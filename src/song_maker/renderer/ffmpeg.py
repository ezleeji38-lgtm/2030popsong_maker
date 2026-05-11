"""FFmpeg 렌더링. 오디오+이미지→MP4 + Gate 5 검증."""

import shutil
import subprocess
from pathlib import Path

from rich.console import Console
from rich.progress import Progress

from song_maker import config as cfg
from song_maker.gates import Check, GateResult
from song_maker.models import Song

console = Console()


def check_ffmpeg() -> bool:
    """FFmpeg 설치 여부 확인."""
    return shutil.which("ffmpeg") is not None


def check_ffprobe() -> bool:
    """ffprobe 설치 여부 확인."""
    return shutil.which("ffprobe") is not None


def get_audio_duration(audio_path: Path) -> float:
    """ffprobe로 오디오 길이(초)를 반환한다. 실패 시 0.0 (경고 출력)."""
    if not check_ffprobe():
        console.print("  [yellow][경고][/yellow] ffprobe 미설치 — 오디오 길이를 알 수 없습니다.")
        return 0.0
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(audio_path)],
            capture_output=True, timeout=10,
            encoding="utf-8", errors="replace",
        )
        out = result.stdout.strip()
        if not out:
            console.print(f"  [yellow][경고][/yellow] ffprobe 응답이 비어있음: {audio_path}")
            return 0.0
        return float(out)
    except Exception as e:
        console.print(f"  [yellow][경고][/yellow] ffprobe 오류({audio_path}): {e}")
        return 0.0


def lyrics_to_srt(lyrics_path: Path, duration: float) -> Path:
    """lyrics.txt → lyrics.srt 변환. 각 줄을 균등 분배."""
    text = lyrics_path.read_text(encoding="utf-8").strip()
    lines = [l for l in text.split("\n") if l.strip()]

    if not lines or duration <= 0:
        return lyrics_path  # 변환 불가 시 원본 반환

    interval = duration / len(lines)
    srt_parts: list[str] = []

    for i, line in enumerate(lines):
        start = _format_srt_time(i * interval)
        end = _format_srt_time((i + 1) * interval)
        srt_parts.append(f"{i + 1}\n{start} --> {end}\n{line}\n")

    srt_path = lyrics_path.with_suffix(".srt")
    srt_path.write_text("\n".join(srt_parts), encoding="utf-8")
    return srt_path


def _format_srt_time(seconds: float) -> str:
    """초 → SRT 타임코드 (HH:MM:SS,mmm)."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def render(
    song: Song,
    song_dir: Path,
    config: dict,
    subtitles: bool = False,
    fade: float = 0,
    resolution: str = "",
) -> Song:
    """오디오 + 배경 이미지를 합쳐 MP4 영상을 생성한다."""
    if not check_ffmpeg():
        raise RuntimeError(
            "FFmpeg가 설치되지 않았습니다. https://ffmpeg.org/download.html"
        )

    audio = song_dir / (song.audio_path or "audio.mp3")
    background = song_dir / (song.background_path or "background.png")
    output = song_dir / "video.mp4"

    if not audio.exists():
        raise FileNotFoundError(f"오디오 파일 없음: {audio}")
    if not background.exists():
        raise FileNotFoundError(f"배경 이미지 없음: {background}")

    res = resolution or cfg.get(config, "render", "resolution") or "1920x1080"
    if fade <= 0:
        fade = float(cfg.get(config, "render", "default_fade") or 0)

    # FFmpeg 명령어 조합
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(background),
        "-i", str(audio),
        "-c:v", "libx264", "-tune", "stillimage",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-s", res,
    ]

    vf_filters: list[str] = []

    # 자막
    srt_path = None
    if subtitles:
        lyrics_path = song_dir / (song.lyrics_path or "lyrics.txt")
        if lyrics_path.exists():
            duration = get_audio_duration(audio)
            srt_path = lyrics_to_srt(lyrics_path, duration)
            font = cfg.get(config, "render", "subtitle_font")
            # FontName에 공백/특수문자가 들어오면 깨질 수 있어 따옴표 안전 처리
            font_clean = font.replace("'", "").replace(",", "") if font else ""
            style = f"FontName={font_clean}," if font_clean else ""
            # FFmpeg lavfi 이스케이프: 백슬래시, 콜론, 그리고 single quote
            srt_escaped = (
                str(srt_path)
                .replace("\\", "/")
                .replace(":", "\\:")
                .replace("'", "\\'")
            )
            vf_filters.append(
                f"subtitles='{srt_escaped}':force_style='{style}FontSize=28,"
                f"PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2,"
                f"Alignment=2,MarginV=50'"
            )

    # 페이드
    if fade > 0:
        duration = get_audio_duration(audio)
        if duration > fade * 2:
            fade_out_start = duration - fade
            vf_filters.append(f"fade=t=in:st=0:d={fade}")
            vf_filters.append(f"fade=t=out:st={fade_out_start:.1f}:d={fade}")
            cmd.extend([
                "-af", f"afade=t=in:st=0:d={fade},afade=t=out:st={fade_out_start:.1f}:d={fade}"
            ])

    if vf_filters:
        cmd.extend(["-vf", ",".join(vf_filters)])

    cmd.extend(["-shortest", str(output)])

    # 실행
    with Progress() as progress:
        task = progress.add_task("영상 렌더링 중...", total=None)
        result = subprocess.run(
            cmd, capture_output=True, timeout=600,
            encoding="utf-8", errors="replace",
        )
        progress.update(task, description="렌더링 완료!", completed=100, total=100)

    if result.returncode != 0:
        error_lines = result.stderr.strip().split("\n")[-5:]
        raise RuntimeError(
            f"FFmpeg 에러 (exit code {result.returncode}):\n"
            + "\n".join(error_lines)
        )

    song.video_path = "video.mp4"
    song.status = "rendered"
    song.render_options = {
        "resolution": res,
        "fade": fade,
        "subtitles": subtitles,
    }
    return song


def _ffprobe_info(video_path: Path) -> dict:
    """ffprobe로 영상 정보를 조회한다."""
    if not check_ffprobe() or not video_path.exists():
        return {}
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", str(video_path)],
            capture_output=True, timeout=10,
            encoding="utf-8", errors="replace",
        )
        import json
        return json.loads(result.stdout)
    except Exception:
        return {}


def verify_gate5(song: Song, song_dir: Path) -> GateResult:
    """Gate 5: 영상 렌더링 결과 검증."""
    checks: list[Check] = []
    video = song_dir / "video.mp4"

    # 5-2. 파일 존재
    checks.append(Check(
        name="video_exists",
        passed=video.exists(),
        message="영상 파일이 생성되지 않았습니다.",
    ))

    if not video.exists():
        return GateResult(gate="gate5", checks=checks)

    # 5-3. 파일 크기
    size_mb = video.stat().st_size / (1024 * 1024)
    checks.append(Check(
        name="video_size",
        passed=0.01 < size_mb < 500,
        message=f"영상 크기가 비정상적입니다. ({size_mb:.1f}MB)",
    ))

    # 5-4, 5-5. 스트림 검증
    info = _ffprobe_info(video)
    streams = info.get("streams", [])

    has_video = any(s.get("codec_type") == "video" for s in streams)
    has_audio = any(s.get("codec_type") == "audio" for s in streams)

    checks.append(Check(
        name="video_stream",
        passed=has_video,
        message="비디오 스트림을 감지할 수 없습니다.",
    ))
    checks.append(Check(
        name="audio_stream",
        passed=has_audio,
        message="오디오 스트림을 감지할 수 없습니다.",
    ))

    # 5-6. 길이 비교 (비차단)
    audio_path = song_dir / (song.audio_path or "audio.mp3")
    if audio_path.exists() and info.get("format"):
        video_dur = float(info["format"].get("duration", 0))
        audio_dur = get_audio_duration(audio_path)
        if audio_dur > 0:
            checks.append(Check(
                name="duration_match",
                passed=abs(video_dur - audio_dur) <= 3.0,
                blocking=False,
                message=f"영상({video_dur:.1f}초)과 오디오({audio_dur:.1f}초) 길이 차이",
            ))

    return GateResult(gate="gate5", checks=checks)
