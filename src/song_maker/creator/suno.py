"""Suno API 연동. 곡 생성, 폴링, 다운로드 + Gate 3 검증.

2가지 모드:
- Simple (/api/generate): 설명문 → Suno가 가사+음악 자동 생성
- Advanced (/api/custom_generate): 실제 가사 + 태그 + 제목 → Suno가 가사를 그대로 노래

흐름:
  가사 키워드 있음 → generate_lyrics로 가사 생성 → custom_generate (Advanced)
  가사 키워드 없음 → generate (Simple)
"""

import shutil
import subprocess
import time
from pathlib import Path

import httpx
from rich.console import Console
from rich.progress import Progress

from song_maker import config as cfg
from song_maker.creator.prompt import (
    build_custom_prompt,
    build_direct_prompt,
    build_lyrics_prompt,
    build_simple_prompt,
)
from song_maker.gates import Check, GateResult
from song_maker.models import Song, SongRequest

console = Console()

POLL_INTERVAL = 15  # 초
POLL_TIMEOUT = 600  # 10분
MAX_RETRIES = 3
RETRY_DELAY = 10  # 초
API_TIMEOUT = 120  # 생성 요청 타임아웃


def generate_song(config: dict, song: Song, song_dir: Path) -> Song:
    """Suno API를 통해 곡을 생성하고 다운로드한다.

    가사 키워드 있으면: generate_lyrics → custom_generate (Advanced)
    가사 키워드 없으면: generate (Simple)
    """
    base_url = cfg.get(config, "suno", "api_url").rstrip("/")

    request = SongRequest(
        genre=song.genre,
        mood=song.mood,
        theme=song.theme,
        lyrics_keywords=song.lyrics_keywords,
        reference_song=song.reference_song,
    )

    # 모드 결정: 가사 키워드 있으면 Advanced, 없으면 Simple
    use_advanced = bool(request.lyrics_keywords)

    if use_advanced:
        console.print("  모드: Advanced (가사 생성 → custom_generate)")
        try:
            lyrics = _generate_lyrics(base_url, request)
        except Exception as e:
            console.print(f"  [yellow]가사 생성 실패: {e}. Simple 모드로 폴백합니다.[/yellow]")
            use_advanced = False
            prompt = build_simple_prompt(request)
        else:
            console.print(f"  생성된 가사: {lyrics[:80]}...")
            (song_dir / "generated_lyrics.txt").write_text(lyrics, encoding="utf-8")
            prompt = build_custom_prompt(request, lyrics)
    else:
        console.print("  모드: Simple (generate)")
        prompt = build_simple_prompt(request)

    # 재시도 루프
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            console.print(f"  생성 시도 {attempt}/{MAX_RETRIES}...")

            # 곡 생성 요청
            endpoint = "custom_generate" if use_advanced else "generate"
            song_ids = _request_generate(base_url, prompt, endpoint)
            console.print(f"  곡 ID: {', '.join(song_ids)}")

            # 폴링 → 2곡 중 완료된 곡 수집
            completed = _poll_until_complete(base_url, song_ids)

            # 가장 좋은 곡 선택
            best = _select_best(completed)
            console.print(f"  선택된 곡: {best.get('id', '?')} (status: {best.get('status', '?')})")

            # 다운로드
            audio_url = best.get("audio_url", "")
            if not audio_url:
                raise RuntimeError("Suno 응답에 audio_url이 없습니다.")

            audio_path = song_dir / "audio.mp3"
            _download_file(audio_url, audio_path)
            song.audio_path = "audio.mp3"

            # 가사 저장 (Suno 응답에서 가져옴)
            actual_lyrics = best.get("lyric", "") or best.get("prompt", "")
            if actual_lyrics:
                lyrics_path = song_dir / "lyrics.txt"
                lyrics_path.write_text(actual_lyrics, encoding="utf-8")
                song.lyrics_path = "lyrics.txt"

            song.status = "created"
            return song

        except Exception as e:
            last_error = e
            console.print(f"  [yellow]시도 {attempt} 실패: {e}[/yellow]")
            if attempt < MAX_RETRIES:
                console.print(f"  {RETRY_DELAY}초 후 재시도...")
                time.sleep(RETRY_DELAY)

    raise RuntimeError(f"곡 생성 {MAX_RETRIES}회 실패: {last_error}")


def get_suno_credits(config: dict) -> dict | None:
    """Suno 래퍼의 /api/get_limit으로 남은 크레딧 조회. 실패 시 None.

    응답 예시: {"credits_left": 4250, "monthly_limit": 10000, ...}
    """
    base_url = cfg.get(config, "suno", "api_url").rstrip("/")
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{base_url}/api/get_limit")
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None


def generate_song_direct(config: dict, song: Song, song_dir: Path) -> Song:
    """시트에서 받은 title/lyrics/tags를 Suno에 직접 주입.

    Song 인스턴스에 suno_title/suno_lyrics/suno_tags가 채워져 있어야 함.
    내부 가사 생성/모드 결정 로직 우회.
    """
    if not song.suno_title or not song.suno_lyrics or not song.suno_tags:
        raise ValueError(
            "direct 모드는 suno_title/suno_lyrics/suno_tags가 모두 필요합니다."
        )

    base_url = cfg.get(config, "suno", "api_url").rstrip("/")
    prompt = build_direct_prompt(
        title=song.suno_title,
        lyrics=song.suno_lyrics,
        tags=song.suno_tags,
        persona_id=song.suno_persona_id,
    )

    # 사전 가사 저장 (Suno 응답 가사가 다를 수 있어 시트 원본 보존)
    (song_dir / "input_lyrics.txt").write_text(song.suno_lyrics, encoding="utf-8")

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            console.print(f"  Suno custom_generate 시도 {attempt}/{MAX_RETRIES}...")
            song_ids = _request_generate(base_url, prompt, "custom_generate")
            console.print(f"  곡 ID: {', '.join(song_ids)}")

            completed = _poll_until_complete(base_url, song_ids)
            best = _select_best(completed)
            console.print(f"  선택된 곡: {best.get('id', '?')} (status: {best.get('status', '?')})")

            audio_url = best.get("audio_url", "")
            if not audio_url:
                raise RuntimeError("Suno 응답에 audio_url이 없습니다.")

            audio_path = song_dir / "audio.mp3"
            _download_file(audio_url, audio_path)

            # Song 메타 갱신
            song.audio_path = "audio.mp3"
            song.suno_audio_url = audio_url
            song.suno_song_id = best.get("id", "")

            # 시트 가사를 그대로 저장 (Suno가 변경했더라도 원본 우선)
            (song_dir / "lyrics.txt").write_text(song.suno_lyrics, encoding="utf-8")
            song.lyrics_path = "lyrics.txt"

            song.status = "created"
            return song

        except Exception as e:
            last_error = e
            console.print(f"  [yellow]시도 {attempt} 실패: {e}[/yellow]")
            if attempt < MAX_RETRIES:
                console.print(f"  {RETRY_DELAY}초 후 재시도...")
                time.sleep(RETRY_DELAY)

    raise RuntimeError(f"곡 생성 {MAX_RETRIES}회 실패: {last_error}")


def _generate_lyrics(base_url: str, request: SongRequest) -> str:
    """Suno /api/generate_lyrics로 가사를 생성한다. 실패 시 RuntimeError."""
    lyrics_prompt = build_lyrics_prompt(request)
    console.print(f"  가사 생성 프롬프트: {lyrics_prompt[:80]}...")

    with httpx.Client(timeout=60) as client:
        resp = client.post(
            f"{base_url}/api/generate_lyrics",
            json={"prompt": lyrics_prompt},
        )
        resp.raise_for_status()
        data = resp.json()

    # 응답: {text: "...", title: "...", status: "complete"}
    lyrics_text = data.get("text", "")
    if not lyrics_text:
        raise RuntimeError(f"가사 생성 응답에 텍스트가 없습니다: {str(data)[:200]}")

    console.print(f"  [green]가사 생성 완료[/green] ({len(lyrics_text)}자)")
    return lyrics_text


def _request_generate(base_url: str, prompt: dict, endpoint: str) -> list[str]:
    """POST /api/generate 또는 /api/custom_generate → 곡 ID 목록 반환."""
    url = f"{base_url}/api/{endpoint}"
    console.print(f"  POST {url}")

    with httpx.Client(timeout=API_TIMEOUT) as client:
        resp = client.post(url, json=prompt)
        resp.raise_for_status()
        data = resp.json()

    # 응답 파싱
    if isinstance(data, list):
        return [item.get("id", "") for item in data if item.get("id")]
    elif isinstance(data, dict):
        if "clips" in data:
            return [clip["id"] for clip in data["clips"]]
        ids = data.get("ids", [])
        if ids:
            return ids
        single_id = data.get("id", "")
        if single_id:
            return [single_id]

    raise RuntimeError(f"예상치 못한 Suno API 응답: {str(data)[:200]}")


def _poll_until_complete(base_url: str, song_ids: list[str]) -> list[dict]:
    """생성 상태를 폴링한다. 모든 곡이 terminal(complete/streaming/error)에 도달하면 종료.

    - 모든 곡이 terminal: 완료된 곡들 반환 (없으면 RuntimeError)
    - POLL_TIMEOUT 도달: 완료된 곡이 1개라도 있으면 반환, 없으면 TimeoutError
    """
    TERMINAL = {"streaming", "complete", "error"}
    start = time.time()
    ids_param = ",".join(song_ids)
    completed: list[dict] = []

    with Progress() as progress:
        task = progress.add_task("곡 생성 중...", total=None)

        while time.time() - start < POLL_TIMEOUT:
            with httpx.Client(timeout=30) as client:
                resp = client.get(f"{base_url}/api/get", params={"ids": ids_param})
                resp.raise_for_status()
                data = resp.json()

            items = data if isinstance(data, list) else data.get("clips", [data])

            completed = []
            errors = 0
            for item in items:
                status = item.get("status", "")
                if status in ("streaming", "complete"):
                    completed.append(item)
                elif status == "error":
                    errors += 1
                    console.print(f"  [red]곡 에러: {item.get('error_message', 'unknown')}[/red]")

            elapsed = int(time.time() - start)
            statuses = ", ".join(item.get("status", "?") for item in items)
            progress.update(task, description=f"곡 생성 중... [{elapsed}s] ({statuses})")

            all_terminal = all(item.get("status", "") in TERMINAL for item in items)
            if all_terminal:
                if completed:
                    progress.update(task, description="곡 생성 완료!", completed=100, total=100)
                    return completed
                raise RuntimeError("모든 곡 생성 실패")

            time.sleep(POLL_INTERVAL)

    if completed:
        console.print(f"  [yellow]타임아웃 도달 — 완료된 {len(completed)}곡으로 진행합니다.[/yellow]")
        return completed
    raise TimeoutError(f"곡 생성 타임아웃 ({POLL_TIMEOUT}초)")


def _select_best(songs: list[dict]) -> dict:
    """2곡 중 가장 좋은 곡을 선택한다. duration이 긴 곡 우선."""
    if len(songs) == 1:
        return songs[0]

    def score(song: dict) -> float:
        dur = song.get("duration", "0") or "0"
        try:
            return float(dur)
        except (ValueError, TypeError):
            return 0.0

    return max(songs, key=score)


def _download_file(url: str, dest: Path) -> None:
    """URL에서 파일을 다운로드한다."""
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in resp.iter_bytes(8192):
                    f.write(chunk)


def _has_audio_stream(audio_path: Path) -> bool:
    """ffprobe로 오디오 스트림 존재 여부를 확인한다."""
    if not shutil.which("ffprobe"):
        return True

    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_streams", "-select_streams", "a", str(audio_path)],
            capture_output=True, timeout=10,
            encoding="utf-8", errors="replace",
        )
        return "codec_name" in result.stdout
    except Exception:
        return True


def verify_gate3(
    song: Song,
    song_dir: Path,
    *,
    duration_min: float = 60.0,
    duration_max: float = 360.0,
    target_min: float = 180.0,
    target_max: float = 210.0,
) -> GateResult:
    """Gate 3: 곡 생성 결과 검증.

    duration 검사:
      - duration_min ~ duration_max: 비차단 통과
      - target_min(3:00) ~ target_max(3:30): 지침서 #11 권장 범위 — 비차단 경고
      - duration_min 미만 또는 duration_max 초과: 차단
    """
    from song_maker.renderer.ffmpeg import get_audio_duration

    checks: list[Check] = []
    audio = song_dir / "audio.mp3"

    checks.append(Check(
        name="audio_file_exists",
        passed=audio.exists(),
        message="오디오 파일이 존재하지 않습니다.",
    ))

    if audio.exists():
        size = audio.stat().st_size
        checks.append(Check(
            name="audio_file_size",
            passed=size > 10_000,
            message=f"오디오 파일이 비정상적으로 작습니다. ({size // 1000}KB)",
        ))

    if audio.exists():
        checks.append(Check(
            name="audio_integrity",
            passed=_has_audio_stream(audio),
            message="오디오 스트림을 감지할 수 없습니다.",
        ))

        # 곡 길이 검증 (지침서 #11: 3:00~3:30 유지)
        duration = get_audio_duration(audio)
        if duration > 0:
            mm_ss = f"{int(duration // 60)}:{int(duration % 60):02d}"
            checks.append(Check(
                name="audio_duration_range",
                passed=duration_min <= duration <= duration_max,
                message=(
                    f"곡 길이 비정상 ({mm_ss}, 허용 {int(duration_min)}~{int(duration_max)}초)"
                ),
            ))
            checks.append(Check(
                name="audio_duration_target",
                passed=target_min <= duration <= target_max,
                blocking=False,  # 권장 범위 — 경고만
                message=(
                    f"곡 길이 {mm_ss} — 지침서 권장(3:00~3:30) 벗어남"
                ),
            ))

    lyrics = song_dir / "lyrics.txt"
    checks.append(Check(
        name="lyrics_exists",
        passed=lyrics.exists() and lyrics.stat().st_size > 0,
        blocking=False,
        message="가사 파일이 없습니다. 가사 없이 진행합니다.",
    ))

    return GateResult(gate="gate3", checks=checks)
