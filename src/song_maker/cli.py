"""CLI 진입점. Typer 앱. 명령어 라우팅."""

import sys
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from song_maker import __version__
from song_maker import config as cfg

app = typer.Typer(
    name="songmaker",
    help="YouTube 트렌드 기반 AI 곡 생성 자동화 CLI 도구",
    no_args_is_help=True,
)
console = Console()


def version_callback(value: bool) -> None:
    if value:
        console.print(f"songmaker v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None, "--version", "-V", callback=version_callback, is_eager=True,
        help="버전 출력",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="상세 로그 출력"),
) -> None:
    """Song Maker CLI."""
    pass


@app.command()
def run(
    region: str = typer.Option("KR", "--region", "-r", help="트렌드 지역 코드"),
    project: str = typer.Option("", "--project", "-p", help="프로젝트 이름"),
    count: int = typer.Option(1, "--count", "-n", help="생성할 곡 수 (1~10)"),
    subtitles: bool = typer.Option(False, "--subtitles", "-s", help="가사 자막 포함"),
    fade: float = typer.Option(2, "--fade", "-f", help="페이드인/아웃 (초)"),
    skip_upload: bool = typer.Option(False, "--skip-upload", help="업로드 건너뛰기"),
    skip_trend: bool = typer.Option(False, "--skip-trend", help="Stage 1 트렌드 조사 무조건 스킵 (대화형 확인 안 함)"),
    with_trend: bool = typer.Option(False, "--with-trend", help="Stage 1 트렌드 조사 무조건 실행 (대화형 확인 안 함)"),
) -> None:
    """전체 파이프라인을 실행합니다. (Stage 1~6)

    기본: Stage 1 트렌드 조사는 매번 대화형 확인 (기본값 N — 스킵).
    --skip-trend 또는 --with-trend로 비대화형 운영 가능.
    """
    from song_maker.gates import Check, GateResult, run_gate
    from song_maker.models import SongRequest
    from song_maker.storage import (
        create_song,
        generate_project_name,
        get_song_dir,
        save_project_meta,
        save_song_meta,
    )

    config = cfg.load_config()
    count = max(1, min(10, count))

    # ========== Stage 1: 트렌드 조사 (선택) ==========
    console.print("\n  [bold]Stage 1: 트렌드 조사[/bold]")
    trend_report = None
    api_key = cfg.get(config, "youtube", "api_key")

    # 트렌드 실행 여부 결정
    do_trend = False
    if skip_trend:
        do_trend = False
    elif with_trend:
        if not api_key:
            console.print("  [red][에러][/red] --with-trend 사용했지만 YouTube API 키 미설정")
            raise typer.Exit(1)
        do_trend = True
    else:
        # 대화형 확인 (기본값 N)
        if not api_key:
            console.print("  [yellow]YouTube API 키 미설정 — 트렌드 조사 자동 스킵[/yellow]")
            do_trend = False
        else:
            do_trend = typer.confirm("  트렌드 조사를 진행할까요?", default=False)

    if do_trend:
        from song_maker.trend.analyzer import analyze, print_report
        from song_maker.trend.youtube import fetch_trending, verify_gate1

        console.print(f"  유튜브 인기 음악 ({region}) 조회 중...\n")
        items = fetch_trending(api_key, region=region)
        trend_report = analyze(items, region=region)

        gate1 = verify_gate1(trend_report)
        if not run_gate(gate1, "트렌드 조사"):
            raise typer.Exit(1)
        print_report(trend_report)
    else:
        console.print("  [dim]트렌드 조사 스킵[/dim]\n")

    # ========== Stage 2: 사용자 입력 ==========
    console.print("\n  [bold]Stage 2: 곡 정보 입력[/bold]\n")

    if trend_report and trend_report.top_genres:
        console.print(f"  트렌드 장르: {', '.join(trend_report.top_genres)}")

    genre = typer.prompt("  장르 (예: 발라드, K-pop, 힙합)")
    mood = typer.prompt("  분위기 (예: 밝은, 슬픈, 몽환적)")
    theme = typer.prompt("  곡의 주제 (예: 봄날의 설렘)")
    keywords_raw = typer.prompt("  가사 키워드 (쉼표 구분, Enter=건너뛰기)", default="")
    lyrics_keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()] if keywords_raw else []
    reference = typer.prompt("  참고곡 (Enter=건너뛰기)", default="")

    request = SongRequest(
        genre=genre, mood=mood, theme=theme,
        lyrics_keywords=lyrics_keywords,
        reference_song=reference or None,
        count=count,
    )

    # Gate 2
    gate2_checks = [
        Check(name="genre", passed=bool(request.genre.strip()), message="장르를 입력해주세요."),
        Check(name="mood", passed=bool(request.mood.strip()), message="분위기를 입력해주세요."),
        Check(name="theme", passed=bool(request.theme.strip()), message="주제를 입력해주세요."),
    ]
    gate2 = GateResult(gate="gate2", checks=gate2_checks)
    if not run_gate(gate2, "사용자 입력"):
        raise typer.Exit(1)

    # 확인
    confirm_table = Table(title="입력 요약")
    confirm_table.add_column("항목", width=15)
    confirm_table.add_column("값", width=35)
    confirm_table.add_row("장르", request.genre)
    confirm_table.add_row("분위기", request.mood)
    confirm_table.add_row("주제", request.theme)
    confirm_table.add_row("가사 키워드", ", ".join(request.lyrics_keywords) or "-")
    confirm_table.add_row("참고곡", request.reference_song or "-")
    confirm_table.add_row("곡 수", str(request.count))
    console.print(confirm_table)

    if not typer.confirm("\n  이 설정으로 진행하시겠습니까?", default=True):
        raise typer.Exit()

    # ========== Stage 3~6: 곡별 처리 ==========
    project_name = project or generate_project_name()
    song_ids: list[str] = []
    results: list[dict] = []

    for i in range(request.count):
        console.print(f"\n  {'=' * 50}")
        console.print(f"  곡 {i + 1}/{request.count}")
        console.print(f"  {'=' * 50}")

        song = create_song(project_name, request)
        song_ids.append(song.id)
        song_dir = get_song_dir(project_name, song.id)
        result_info = {"id": song.id, "status": "failed"}

        # --- Stage 3: 곡 생성 ---
        console.print(f"\n  [bold]Stage 3: 곡 생성[/bold] (ID: {song.id})")
        try:
            from song_maker.creator.suno import generate_song, verify_gate3

            song = generate_song(config, song, song_dir)
            save_song_meta(project_name, song)
            console.print(f"  [green]오디오 저장[/green]: {song.audio_path}")

            gate3 = verify_gate3(song, song_dir)
            song.gates["gate3"] = gate3.to_dict()
            if not run_gate(gate3, "곡 생성"):
                save_song_meta(project_name, song)
                results.append(result_info)
                continue
        except Exception as e:
            console.print(f"  [red][에러][/red] 곡 생성 실패: {e}")
            console.print("  songmaker import <mp3> 로 수동 임포트할 수 있습니다.")
            save_song_meta(project_name, song)
            results.append(result_info)
            continue

        # --- Stage 4: 이미지 생성 ---
        console.print(f"\n  [bold]Stage 4: 이미지 생성[/bold]")
        gemini_key = cfg.get(config, "gemini", "api_key")
        if gemini_key:
            try:
                from song_maker.imager.gemini import generate_images, verify_gate4

                song = generate_images(config, song, song_dir)
                console.print(f"  [green]이미지 저장[/green]: {song.background_path}")

                gate4 = verify_gate4(song, song_dir)
                song.gates["gate4"] = gate4.to_dict()
                if not run_gate(gate4, "이미지 생성"):
                    save_song_meta(project_name, song)
                    results.append(result_info)
                    continue
            except Exception as e:
                console.print(f"  [yellow][경고][/yellow] 이미지 생성 실패: {e}")
        else:
            console.print("  [yellow][경고][/yellow] Gemini API 키 미설정. 건너뜁니다.")

        save_song_meta(project_name, song)

        # --- Stage 5: 렌더링 ---
        if song.audio_path and song.background_path:
            console.print(f"\n  [bold]Stage 5: 영상 렌더링[/bold]")
            try:
                from song_maker.renderer.ffmpeg import render as do_render, verify_gate5

                song = do_render(song, song_dir, config, subtitles=subtitles, fade=fade)
                console.print(f"  [green]영상 저장[/green]: {song.video_path}")

                gate5 = verify_gate5(song, song_dir)
                song.gates["gate5"] = gate5.to_dict()
                if not run_gate(gate5, "렌더링"):
                    save_song_meta(project_name, song)
                    results.append(result_info)
                    continue
            except Exception as e:
                console.print(f"  [red][에러][/red] 렌더링 실패: {e}")
                save_song_meta(project_name, song)
                results.append(result_info)
                continue
        else:
            console.print("\n  [yellow][경고][/yellow] 오디오 또는 배경 이미지 없음. 렌더링을 건너뜁니다.")

        save_song_meta(project_name, song)

        # --- Stage 6: 업로드 ---
        if song.video_path and not skip_upload:
            console.print(f"\n  [bold]Stage 6: YouTube 업로드[/bold]")
            privacy = cfg.get(config, "upload", "default_privacy") or "private"
            try:
                from song_maker.uploader.youtube import upload as do_upload, verify_gate6

                song = do_upload(song, song_dir, privacy=privacy)

                gate6 = verify_gate6(song)
                song.gates["gate6"] = gate6.to_dict()
                run_gate(gate6, "업로드")

                console.print(f"  [green]업로드 완료[/green] ({privacy}): {song.youtube_url}")
                result_info["url"] = song.youtube_url
            except Exception as e:
                console.print(f"  [red][에러][/red] 업로드 실패: {e}")
                console.print(f"  수동 업로드: songmaker upload {song.id}")
        elif skip_upload:
            console.print("\n  업로드 건너뛰기 (--skip-upload)")

        save_song_meta(project_name, song)
        result_info["status"] = song.status
        results.append(result_info)

    # ========== 결과 요약 ==========
    save_project_meta(project_name, song_ids)

    console.print(f"\n  {'=' * 50}")
    console.print(f"  [bold]완료![/bold] 프로젝트: {project_name}")
    console.print(f"  {'=' * 50}")

    for r in results:
        url = r.get("url", "")
        url_str = f" → {url}" if url else ""
        console.print(f"  곡 {r['id']}: {r['status']}{url_str}")


@app.command()
def trend(
    region: str = typer.Option("KR", "--region", "-r", help="트렌드 지역 코드"),
    count: int = typer.Option(20, "--count", "-n", help="조회할 곡 수 (최대 50)"),
) -> None:
    """YouTube 인기 음악 트렌드를 조회합니다."""
    from song_maker.gates import run_gate
    from song_maker.trend.analyzer import analyze, print_report
    from song_maker.trend.youtube import fetch_trending

    config = cfg.load_config()
    api_key = cfg.get(config, "youtube", "api_key")

    if not api_key:
        console.print("[red][에러][/red] YouTube API 키가 설정되지 않았습니다.")
        console.print("  songmaker config 명령으로 설정하세요.")
        raise typer.Exit(1)

    console.print(f"\n  유튜브 인기 음악 ({region}) 조회 중...\n")

    items = fetch_trending(api_key, region=region, max_results=count)
    report = analyze(items, region=region)

    # Gate 1 검증
    from song_maker.trend.youtube import verify_gate1

    gate_result = verify_gate1(report)
    if not run_gate(gate_result, "트렌드 조사"):
        raise typer.Exit(1)

    print_report(report)


@app.command()
def create(
    region: str = typer.Option("KR", "--region", "-r", help="트렌드 지역 코드"),
    project: str = typer.Option("", "--project", "-p", help="프로젝트 이름"),
    skip_trend: bool = typer.Option(False, "--skip-trend", help="Stage 1 트렌드 조사 무조건 스킵"),
    with_trend: bool = typer.Option(False, "--with-trend", help="Stage 1 트렌드 조사 무조건 실행"),
) -> None:
    """트렌드 조사 → 사용자 입력 → 곡 생성 → 이미지 생성.

    Stage 1 트렌드 조사는 매번 대화형 확인 (기본값 N — 스킵).
    """
    from song_maker.gates import Check, GateResult, run_gate
    from song_maker.models import SongRequest
    from song_maker.storage import (
        create_song,
        generate_project_name,
        get_song_dir,
        save_project_meta,
        save_song_meta,
    )

    config = cfg.load_config()

    # --- Stage 1: 트렌드 조사 (선택) ---
    trend_report = None
    api_key = cfg.get(config, "youtube", "api_key")

    do_trend = False
    if skip_trend:
        do_trend = False
    elif with_trend:
        if not api_key:
            console.print("  [red][에러][/red] --with-trend 사용했지만 YouTube API 키 미설정")
            raise typer.Exit(1)
        do_trend = True
    else:
        if not api_key:
            console.print("  [yellow]YouTube API 키 미설정 — 트렌드 조사 자동 스킵[/yellow]")
            do_trend = False
        else:
            do_trend = typer.confirm("\n  트렌드 조사를 진행할까요?", default=False)

    if do_trend:
        from song_maker.trend.analyzer import analyze, print_report
        from song_maker.trend.youtube import fetch_trending, verify_gate1

        console.print(f"\n  유튜브 인기 음악 ({region}) 조회 중...\n")
        items = fetch_trending(api_key, region=region)
        trend_report = analyze(items, region=region)

        gate_result = verify_gate1(trend_report)
        run_gate(gate_result, "트렌드 조사")
        print_report(trend_report)

    # --- Stage 2: 사용자 입력 ---
    console.print("\n  곡 정보 입력\n")

    # 장르 선택
    if trend_report and trend_report.top_genres:
        console.print(f"  트렌드 장르: {', '.join(trend_report.top_genres)}")
    genre = typer.prompt("  장르 (예: 발라드, K-pop, 힙합)")
    mood = typer.prompt("  분위기 (예: 밝은, 슬픈, 몽환적, 에너지틱)")
    theme = typer.prompt("  곡의 주제 (예: 봄날의 설렘)")

    keywords_raw = typer.prompt("  가사 키워드 (쉼표 구분, Enter=건너뛰기)", default="")
    lyrics_keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()] if keywords_raw else []

    reference = typer.prompt("  참고곡 (Enter=건너뛰기)", default="")
    count = typer.prompt("  생성할 곡 수 (1~10)", default="1")

    try:
        count_int = int(count)
        count_int = max(1, min(10, count_int))
    except ValueError:
        count_int = 1

    request = SongRequest(
        genre=genre,
        mood=mood,
        theme=theme,
        lyrics_keywords=lyrics_keywords,
        reference_song=reference or None,
        count=count_int,
    )

    # Gate 2: 입력 검증
    gate2_checks = [
        Check(name="genre", passed=bool(request.genre.strip()), message="장르를 입력해주세요."),
        Check(name="mood", passed=bool(request.mood.strip()), message="분위기를 입력해주세요."),
        Check(name="theme", passed=bool(request.theme.strip()), message="주제를 입력해주세요."),
    ]
    gate2 = GateResult(gate="gate2", checks=gate2_checks)
    if not run_gate(gate2, "사용자 입력"):
        raise typer.Exit(1)

    # 입력 확인
    confirm_table = Table(title="입력 요약")
    confirm_table.add_column("항목", width=15)
    confirm_table.add_column("값", width=35)
    confirm_table.add_row("장르", request.genre)
    confirm_table.add_row("분위기", request.mood)
    confirm_table.add_row("주제", request.theme)
    confirm_table.add_row("가사 키워드", ", ".join(request.lyrics_keywords) or "-")
    confirm_table.add_row("참고곡", request.reference_song or "-")
    confirm_table.add_row("곡 수", str(request.count))
    console.print(confirm_table)

    if not typer.confirm("\n  이 설정으로 진행하시겠습니까?", default=True):
        console.print("  취소되었습니다.")
        raise typer.Exit()

    # --- Stage 3 + 4: 곡 생성 + 이미지 생성 ---
    project_name = project or generate_project_name()
    song_ids: list[str] = []

    for i in range(request.count):
        if request.count > 1:
            console.print(f"\n  --- 곡 {i + 1}/{request.count} ---")

        song = create_song(project_name, request)
        song_ids.append(song.id)
        song_dir = get_song_dir(project_name, song.id)

        # Stage 3: Suno 곡 생성
        try:
            from song_maker.creator.suno import generate_song

            console.print(f"\n  곡 생성 중... (ID: {song.id})")
            song = generate_song(config, song, song_dir)
            save_song_meta(project_name, song)
            console.print(f"  [green]오디오 저장[/green]: {song_dir / 'audio.mp3'}")
        except Exception as e:
            console.print(f"  [red][에러][/red] 곡 생성 실패: {e}")
            console.print("  songmaker import <mp3> 로 수동 임포트할 수 있습니다.")
            save_song_meta(project_name, song)
            continue

        # Gate 3 검증
        from song_maker.creator.suno import verify_gate3

        gate3 = verify_gate3(song, song_dir)
        song.gates["gate3"] = gate3.to_dict()
        if not run_gate(gate3, "곡 생성"):
            save_song_meta(project_name, song)
            continue

        # Stage 4: Gemini 이미지 생성
        gemini_key = cfg.get(config, "gemini", "api_key")
        if gemini_key:
            try:
                from song_maker.imager.gemini import generate_images

                console.print("\n  배경 이미지 생성 중...")
                song = generate_images(config, song, song_dir)
                console.print(f"  [green]이미지 저장[/green]: {song_dir / 'background.png'}")
            except Exception as e:
                console.print(f"  [yellow][경고][/yellow] 이미지 생성 실패: {e}")

            # Gate 4 검증
            from song_maker.imager.gemini import verify_gate4

            gate4 = verify_gate4(song, song_dir)
            song.gates["gate4"] = gate4.to_dict()
            run_gate(gate4, "이미지 생성")
        else:
            console.print("  [yellow][경고][/yellow] Gemini API 키 미설정. 이미지 생성을 건너뜁니다.")

        save_song_meta(project_name, song)

    save_project_meta(project_name, song_ids)
    console.print(f"\n  [green]완료![/green] 프로젝트: {project_name}, 곡 {len(song_ids)}개 생성")
    for sid in song_ids:
        console.print(f"    songmaker image {sid}  (이미지 재생성)")
        console.print(f"    songmaker render {sid} (렌더링)")


@app.command()
def image(
    song_id: str = typer.Argument(..., help="곡 ID"),
) -> None:
    """곡의 배경 이미지와 썸네일을 (재)생성합니다."""
    from song_maker.gates import run_gate
    from song_maker.storage import save_song_meta

    config = cfg.load_config()
    gemini_key = cfg.get(config, "gemini", "api_key")
    if not gemini_key:
        console.print("[red][에러][/red] Gemini API 키가 설정되지 않았습니다.")
        console.print("  songmaker config 명령으로 설정하세요.")
        raise typer.Exit(1)

    project_name, song, song_dir = _find_song(song_id)

    console.print(f"\n  이미지 (재)생성 중... (ID: {song.id})")
    try:
        from song_maker.imager.gemini import generate_images, verify_gate4

        song = generate_images(config, song, song_dir)
        console.print(f"  [green]배경 저장[/green]: {song_dir / 'background.png'}")
        console.print(f"  [green]썸네일 저장[/green]: {song_dir / 'thumbnail.png'}")

        gate4 = verify_gate4(song, song_dir)
        song.gates["gate4"] = gate4.to_dict()
        run_gate(gate4, "이미지 생성")
    except Exception as e:
        console.print(f"  [red][에러][/red] 이미지 생성 실패: {e}")
        raise typer.Exit(1)

    save_song_meta(project_name, song)
    console.print(f"  다음 단계: songmaker render {song.id}")


@app.command(name="import")
def import_mp3(
    mp3_path: str = typer.Argument(..., help="MP3 파일 경로"),
    genre: str = typer.Option(..., "--genre", "-g", help="장르"),
    mood: str = typer.Option(..., "--mood", "-m", help="분위기"),
    theme: str = typer.Option(..., "--theme", "-t", help="주제"),
    lyrics: str = typer.Option("", "--lyrics", "-l", help="가사 파일 경로"),
    project: str = typer.Option("", "--project", "-p", help="프로젝트 이름"),
) -> None:
    """MP3 파일을 수동 임포트합니다. (Suno 대안)"""
    import shutil
    from pathlib import Path

    from song_maker.models import SongRequest
    from song_maker.storage import (
        create_song,
        generate_project_name,
        get_song_dir,
        save_project_meta,
        save_song_meta,
    )

    src = Path(mp3_path)
    if not src.exists():
        console.print(f"[red][에러][/red] 파일을 찾을 수 없습니다: {mp3_path}")
        raise typer.Exit(1)

    project_name = project or generate_project_name()
    request = SongRequest(genre=genre, mood=mood, theme=theme)
    song = create_song(project_name, request)
    song_dir = get_song_dir(project_name, song.id)

    # MP3 복사
    dest = song_dir / "audio.mp3"
    shutil.copy2(src, dest)
    song.audio_path = "audio.mp3"
    song.status = "created"

    # 가사 파일 복사 (선택)
    if lyrics:
        lyrics_src = Path(lyrics)
        if lyrics_src.exists():
            shutil.copy2(lyrics_src, song_dir / "lyrics.txt")
            song.lyrics_path = "lyrics.txt"

    save_song_meta(project_name, song)
    save_project_meta(project_name, [song.id])

    console.print(f"\n  [green]임포트 완료![/green]")
    console.print(f"  프로젝트: {project_name}")
    console.print(f"  곡 ID: {song.id}")
    console.print(f"  다음 단계: songmaker image {song.id}")


def _find_song(song_id: str) -> tuple[str, "Song", "Path"]:
    """song_id로 프로젝트명, Song, song_dir를 찾는다."""
    from song_maker.storage import list_all_songs, get_song_dir

    for project_name, song in list_all_songs():
        if song.id == song_id or song.id.startswith(song_id):
            song_dir = get_song_dir(project_name, song.id)
            return project_name, song, song_dir

    console.print(f"[red][에러][/red] 곡을 찾을 수 없습니다: {song_id}")
    console.print("  songmaker list-songs 로 곡 목록을 확인하세요.")
    raise typer.Exit(1)


@app.command()
def render(
    song_id: str = typer.Argument(..., help="곡 ID"),
    subtitles: bool = typer.Option(False, "--subtitles", "-s", help="가사 자막 포함"),
    fade: float = typer.Option(0, "--fade", "-f", help="페이드인/아웃 (초)"),
    resolution: str = typer.Option("", "--resolution", help="해상도 (예: 1920x1080)"),
) -> None:
    """곡을 MP4 영상으로 렌더링합니다."""
    from song_maker.gates import run_gate
    from song_maker.renderer.ffmpeg import render as do_render, verify_gate5
    from song_maker.storage import save_song_meta

    config = cfg.load_config()
    project_name, song, song_dir = _find_song(song_id)

    if not song.audio_path:
        console.print("[red][에러][/red] 오디오 파일이 없습니다. 먼저 곡을 생성하세요.")
        raise typer.Exit(1)

    if not song.background_path:
        console.print("[red][에러][/red] 배경 이미지가 없습니다. songmaker image 를 먼저 실행하세요.")
        raise typer.Exit(1)

    console.print(f"\n  영상 렌더링 중... (ID: {song.id})")
    try:
        song = do_render(song, song_dir, config, subtitles=subtitles, fade=fade, resolution=resolution)
    except Exception as e:
        console.print(f"  [red][에러][/red] 렌더링 실패: {e}")
        raise typer.Exit(1)

    # Gate 5
    gate5 = verify_gate5(song, song_dir)
    song.gates["gate5"] = gate5.to_dict()
    if not run_gate(gate5, "렌더링"):
        save_song_meta(project_name, song)
        raise typer.Exit(1)

    save_song_meta(project_name, song)
    console.print(f"  [green]영상 저장[/green]: {song_dir / 'video.mp4'}")
    console.print(f"  다음 단계: songmaker upload {song.id}")


@app.command()
def upload(
    song_id: str = typer.Argument(..., help="곡 ID"),
    privacy: str = typer.Option("private", "--privacy", help="공개 설정 (private/unlisted/public)"),
) -> None:
    """영상을 YouTube에 업로드합니다."""
    from song_maker.gates import run_gate
    from song_maker.storage import save_song_meta
    from song_maker.uploader.youtube import upload as do_upload, verify_gate6, set_public

    project_name, song, song_dir = _find_song(song_id)

    if not song.video_path:
        console.print("[red][에러][/red] 영상 파일이 없습니다. songmaker render 를 먼저 실행하세요.")
        raise typer.Exit(1)

    console.print(f"\n  YouTube 업로드 중... (ID: {song.id})")
    try:
        song = do_upload(song, song_dir, privacy=privacy)
    except FileNotFoundError as e:
        console.print(f"  [red][에러][/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"  [red][에러][/red] 업로드 실패: {e}")
        raise typer.Exit(1)

    # Gate 6
    gate6 = verify_gate6(song)
    song.gates["gate6"] = gate6.to_dict()
    run_gate(gate6, "업로드")

    save_song_meta(project_name, song)
    console.print(f"  [green]업로드 완료[/green] ({privacy}): {song.youtube_url}")

    # 공개 전환 확인
    if privacy == "private":
        if typer.confirm("\n  공개로 전환하시겠습니까?", default=False):
            video_id = song.youtube_url.split("/")[-1] if song.youtube_url else ""
            if video_id:
                set_public(video_id)
                console.print("  [green]공개로 전환되었습니다.[/green]")


@app.command()
def status(
    song_id: str = typer.Argument(..., help="곡 ID"),
) -> None:
    """곡 상태 및 Gate 검증 이력을 표시합니다."""
    project_name, song, song_dir = _find_song(song_id)

    # 곡 정보
    info_table = Table(title=f"곡 상태: {song.id}")
    info_table.add_column("항목", width=15)
    info_table.add_column("값", width=40)
    info_table.add_row("프로젝트", project_name)
    info_table.add_row("장르", song.genre)
    info_table.add_row("분위기", song.mood)
    info_table.add_row("주제", song.theme)
    info_table.add_row("상태", song.status)
    info_table.add_row("오디오", song.audio_path or "-")
    info_table.add_row("배경", song.background_path or "-")
    info_table.add_row("썸네일", song.thumbnail_path or "-")
    info_table.add_row("영상", song.video_path or "-")
    info_table.add_row("YouTube", song.youtube_url or "-")
    console.print(info_table)

    # Gate 이력
    if song.gates:
        gate_table = Table(title="Gate 검증 이력")
        gate_table.add_column("Gate", width=8)
        gate_table.add_column("결과", width=8)
        gate_table.add_column("시간", width=22)
        gate_table.add_column("비고", width=30)

        for gate_name in ["gate1", "gate2", "gate3", "gate4", "gate5", "gate6"]:
            gate_data = song.gates.get(gate_name)
            if gate_data:
                passed = "통과" if gate_data.get("passed") else "실패"
                ts = gate_data.get("timestamp", "-")[:19]
                warnings = gate_data.get("warnings", [])
                failures = gate_data.get("failures", [])
                note = ", ".join(warnings + failures) if (warnings or failures) else ""
                gate_table.add_row(gate_name.upper().replace("GATE", "Gate "), passed, ts, note[:30])
            else:
                gate_table.add_row(gate_name.upper().replace("GATE", "Gate "), "대기", "-", "")

        console.print(gate_table)


@app.command()
def doctor() -> None:
    """외부 의존성 사전점검 — FFmpeg, Suno 래퍼, Gemini 키, GCP SA, YouTube OAuth, 시트 접근."""
    import shutil
    from pathlib import Path as _Path

    from song_maker.creator.suno import get_suno_credits

    config = cfg.load_config()
    issues: list[tuple[str, str]] = []  # (severity, message)

    console.print("\n  [bold]songmaker doctor[/bold] — 외부 의존성 점검\n")

    # 1. FFmpeg / ffprobe
    if shutil.which("ffmpeg"):
        console.print("  [green]✓[/green] FFmpeg 설치됨")
    else:
        console.print("  [red]✗[/red] FFmpeg 없음 — `brew install ffmpeg`")
        issues.append(("error", "FFmpeg 미설치"))
    if shutil.which("ffprobe"):
        console.print("  [green]✓[/green] ffprobe 설치됨")
    else:
        console.print("  [red]✗[/red] ffprobe 없음 (FFmpeg 패키지에 보통 포함)")
        issues.append(("error", "ffprobe 미설치"))

    # 2. Gemini API 키
    gemini_key = cfg.get(config, "gemini", "api_key") or ""
    if gemini_key.strip():
        console.print(f"  [green]✓[/green] Gemini API 키 설정됨 ({cfg.mask_key(gemini_key)})")
    else:
        console.print("  [yellow]![/yellow] Gemini API 키 미설정 (이미지 생성/번역 불가)")
        issues.append(("warning", "Gemini 키 미설정"))

    # 3. Suno 래퍼 연결 + 크레딧
    suno_url = cfg.get(config, "suno", "api_url") or ""
    if suno_url:
        info = get_suno_credits(config)
        if info is not None:
            credits_left = info.get("credits_left", info.get("credits", "?"))
            console.print(f"  [green]✓[/green] Suno 래퍼 연결됨 ({suno_url}) — 잔여 크레딧: {credits_left}")
        else:
            console.print(f"  [red]✗[/red] Suno 래퍼 연결 실패 ({suno_url})")
            console.print("       Docker 실행 중인지, SUNO_COOKIE 유효한지 확인")
            issues.append(("error", "Suno 래퍼 연결 실패"))

    # 4. YouTube OAuth client_secret.json
    cs = cfg.CONFIG_DIR / "client_secret.json"
    if cs.exists():
        console.print(f"  [green]✓[/green] YouTube client_secret.json 존재 ({cs})")
    else:
        console.print(f"  [yellow]![/yellow] YouTube client_secret.json 없음 ({cs})")
        console.print("       Google Cloud Console에서 OAuth Desktop 클라이언트 생성 후 저장")
        issues.append(("warning", "YouTube OAuth 미설정"))

    # 5. YouTube token.json (있으면 인증된 상태)
    tk = cfg.CONFIG_DIR / "token.json"
    if tk.exists():
        console.print(f"  [green]✓[/green] YouTube token 있음 (이전 인증 완료)")
        # 권한 점검
        import stat
        mode = tk.stat().st_mode
        if mode & (stat.S_IRWXG | stat.S_IRWXO):
            console.print("       [yellow]경고[/yellow]: token.json 권한이 너무 열림 — 자동으로 chmod 0o600 필요")
    else:
        console.print("  [yellow]![/yellow] YouTube token.json 없음 (첫 upload 시 OAuth 필요)")

    # 6. GCP Service Account JSON (시트/Drive용)
    sa_path_str = cfg.get(config, "sheets", "service_account_path") or ""
    if sa_path_str:
        sa_path = _Path(sa_path_str).expanduser()
        if sa_path.exists():
            console.print(f"  [green]✓[/green] Service Account JSON 존재 ({sa_path})")
            import json as _json
            try:
                sa_data = _json.loads(sa_path.read_text())
                client_email = sa_data.get("client_email", "?")
                console.print(f"       SA 이메일: {client_email}")
                console.print(f"       → 사용할 시트에 이 이메일을 편집자로 공유했는지 확인")
            except Exception as e:
                console.print(f"  [red]✗[/red] SA JSON 파싱 실패: {e}")
                issues.append(("error", "SA JSON 파일 손상"))
        else:
            console.print(f"  [red]✗[/red] Service Account JSON 없음 ({sa_path})")
            issues.append(("error", "SA JSON 미설정"))
    else:
        console.print("  [yellow]![/yellow] Service Account 경로 미설정 (시트/Drive 사용 불가)")
        issues.append(("warning", "SA 경로 미설정"))

    # 7. 기본 시트 ID + 실제 접근 시도
    sheet_id = cfg.get(config, "sheets", "default_sheet_id") or ""
    if sheet_id:
        if sa_path_str and _Path(sa_path_str).expanduser().exists():
            try:
                from song_maker.sheet import open_sheet, verify_schema, HEADERS
                ws = open_sheet(sa_path_str, sheet_id)
                ok, schema_issues = verify_schema(ws)
                if ok:
                    rec_count = len(ws.col_values(1)) - 1  # 헤더 제외
                    console.print(f"  [green]✓[/green] 시트 접근 OK ({rec_count}행 데이터)")
                else:
                    console.print(f"  [red]✗[/red] 시트 헤더 스키마 불일치:")
                    for i in schema_issues:
                        console.print(f"       {i}")
                    console.print(f"       올바른 헤더: {' | '.join(HEADERS)}")
                    issues.append(("error", "시트 헤더 스키마 불일치"))
            except Exception as e:
                console.print(f"  [red]✗[/red] 시트 접근 실패: {type(e).__name__}: {e}")
                issues.append(("error", "시트 접근 실패"))
    else:
        console.print("  [yellow]![/yellow] 기본 시트 ID 미설정")

    # 8. CapCut 폴더
    from song_maker.capcut import capcut_paths
    paths = capcut_paths(config)
    paths.inbox_root.mkdir(parents=True, exist_ok=True)
    paths.outbox_root.mkdir(parents=True, exist_ok=True)
    console.print(f"  [green]✓[/green] CapCut inbox: {paths.inbox_root}")
    console.print(f"  [green]✓[/green] CapCut outbox: {paths.outbox_root}")

    # 8-1. 출력 디렉토리
    from song_maker.storage import _resolve_output_dir
    out_dir = _resolve_output_dir()
    console.print(f"  [green]✓[/green] 출력 디렉토리: {out_dir}")
    if not (cfg.get(config, "output", "dir") or "").strip():
        console.print("       (config 미지정 — cwd 기반. cron 사용 시 [output] dir 지정 권장)")

    # 9. Drive 아카이브 (선택)
    if cfg.get(config, "drive", "archive_enabled") in (True, "true", "True", "1"):
        drive_parent = cfg.get(config, "drive", "lyrics_parent_folder_id") or ""
        if not drive_parent:
            console.print("  [yellow]![/yellow] Drive 아카이브 활성화됐지만 parent_folder_id 미설정")
        else:
            console.print(f"  [green]✓[/green] Drive 아카이브 활성화 (folder_id={drive_parent[:12]}...)")

    # 결과 요약
    console.print(f"\n  {'=' * 60}")
    errors = [i for i in issues if i[0] == "error"]
    warnings = [i for i in issues if i[0] == "warning"]
    if errors:
        console.print(f"  [red][결과][/red] 에러 {len(errors)}건, 경고 {len(warnings)}건 — 운영 불가")
        for sev, msg in errors:
            console.print(f"    [red]ERROR[/red] {msg}")
        raise typer.Exit(1)
    elif warnings:
        console.print(f"  [yellow][결과][/yellow] 에러 없음, 경고 {len(warnings)}건 — 운영 가능 (일부 기능 제한)")
        for sev, msg in warnings:
            console.print(f"    [yellow]WARN[/yellow] {msg}")
    else:
        console.print(f"  [green][결과][/green] 모든 외부 의존성 OK — 운영 준비 완료")


@app.command(name="append-row")
def append_row(
    chatbot_output: str = typer.Argument("", help="챗봇 출력 텍스트 파일 경로 (없으면 stdin 사용)"),
    sheet: str = typer.Option("", "--sheet", "-s", help="시트 ID (비우면 config 기본값)"),
    title: str = typer.Option("", "--title", help="제목 직접 지정 (파일 파싱 결과 덮어쓰기)"),
    tags: str = typer.Option("", "--tags", help="tags 직접 지정"),
    lyrics_file: str = typer.Option("", "--lyrics-file", help="가사 파일 직접 지정"),
    persona_id: str = typer.Option("", "--persona-id", help="Suno persona UUID"),
    image_prompt: str = typer.Option("", "--image-prompt", help="배경 이미지 프롬프트 (선택)"),
    thumbnail_path: str = typer.Option("", "--thumbnail-path", help="외부 썸네일 PNG 경로 (선택)"),
    skip_duplicate: bool = typer.Option(False, "--allow-duplicate", help="중복 검사 건너뛰기"),
    duplicate_threshold: float = typer.Option(0.75, "--duplicate-threshold", help="중복 임계값"),
) -> None:
    """챗봇 출력을 lint+중복 검사 후 시트에 한 행 추가.

    사용법:
      1) 챗봇 출력 파일을 경로로:
         songmaker append-row chatbot_output.txt

      2) stdin pipe:
         pbpaste | songmaker append-row -
         (또는 cat output.txt | songmaker append-row -)

      3) 명시적 지정:
         songmaker append-row \\
           --title "Midnight Replay" \\
           --tags "95 BPM, Modern Pop, Female vocal" \\
           --lyrics-file lyrics.txt
    """
    from pathlib import Path as _Path
    from song_maker.sheet import (
        HEADERS,
        append_pending_row,
        open_sheet,
        parse_chatbot_output,
        verify_schema,
    )
    from song_maker.storage import OUTPUT_DIR
    from song_maker.validation import (
        check_duplicate,
        lint_row,
        load_existing_lyrics,
    )

    config = cfg.load_config()

    # 1. 입력 결정 (파일/stdin/플래그) — 시트 연결보다 먼저 (빨리 실패하기)
    parsed_title = title
    parsed_tags = tags
    parsed_lyrics = ""
    parsed_persona = persona_id

    if lyrics_file:
        lp = _Path(lyrics_file).expanduser()
        if not lp.exists():
            console.print(f"[red][에러][/red] 가사 파일 없음: {lp}")
            raise typer.Exit(1)
        parsed_lyrics = lp.read_text(encoding="utf-8")

    # 챗봇 출력 파일 또는 stdin
    if chatbot_output:
        if chatbot_output == "-":
            text = sys.stdin.read()
        else:
            cp = _Path(chatbot_output).expanduser()
            if not cp.exists():
                console.print(f"[red][에러][/red] 챗봇 출력 파일 없음: {cp}")
                raise typer.Exit(1)
            text = cp.read_text(encoding="utf-8")

        parsed = parse_chatbot_output(text)
        if not parsed_title:
            parsed_title = parsed.title
        if not parsed_tags:
            parsed_tags = parsed.tags
        if not parsed_lyrics:
            parsed_lyrics = parsed.lyrics
        if not parsed_persona:
            parsed_persona = parsed.persona_id

    # 검증
    if not parsed_title:
        console.print("[red][에러][/red] title 추출 실패. --title 명시 또는 챗봇 출력에 'TITLE:' 필요")
        raise typer.Exit(1)
    if not parsed_tags:
        console.print("[red][에러][/red] tags 추출 실패. --tags 명시 또는 챗봇 출력에 'TAGS:' 필요")
        raise typer.Exit(1)
    if not parsed_lyrics:
        console.print("[red][에러][/red] lyrics 추출 실패. --lyrics-file 명시 또는 챗봇 출력에 'LYRICS:' 블록 필요")
        raise typer.Exit(1)

    console.print(f"\n  [bold]파싱 결과[/bold]")
    console.print(f"    title: {parsed_title[:60]}")
    console.print(f"    tags: {parsed_tags}")
    console.print(f"    lyrics: {len(parsed_lyrics)}자 ({parsed_lyrics.count(chr(10)) + 1}줄)")
    if parsed_persona:
        console.print(f"    persona_id: {parsed_persona}")

    # 2. lint
    row_dict = {
        "title": parsed_title,
        "tags": parsed_tags,
        "lyrics": parsed_lyrics,
    }
    issues = lint_row(row_dict)
    errors = [i for i in issues if i.severity == "error"]
    warns = [i for i in issues if i.severity == "warning"]
    console.print(f"\n  [bold]lint[/bold] (error {len(errors)}, warn {len(warns)})")
    for i in issues:
        color = "red" if i.severity == "error" else "yellow"
        console.print(f"    [{color}]{i}[/{color}]")
    if errors:
        console.print("[red][중단][/red] lint 에러로 시트 추가 안 함")
        raise typer.Exit(1)

    # 3. 시트 연결 + 중복 검사
    sheet_id = sheet or cfg.get(config, "sheets", "default_sheet_id")
    if not sheet_id:
        console.print("[red][에러][/red] --sheet <ID> 또는 config 기본값 필요")
        raise typer.Exit(1)

    sa_path = cfg.get(config, "sheets", "service_account_path") or ""
    worksheet_name = cfg.get(config, "sheets", "worksheet") or None

    try:
        ws = open_sheet(sa_path, sheet_id, worksheet_name)
    except Exception as e:
        console.print(f"[red][에러][/red] 시트 열기 실패: {e}")
        raise typer.Exit(1)

    ok, schema_issues = verify_schema(ws)
    if not ok:
        console.print("[red][에러][/red] 시트 헤더 스키마 불일치")
        for i in schema_issues:
            console.print(f"    {i}")
        raise typer.Exit(1)

    if not skip_duplicate:
        all_records = ws.get_all_records()
        sheet_lyrics_history = []
        for idx, rec in enumerate(all_records, start=2):
            st = (rec.get("status") or "").strip().lower()
            if st in ("done", "pending") and rec.get("lyrics"):
                sheet_lyrics_history.append((str(idx), rec.get("title") or "", rec["lyrics"]))
        existing = load_existing_lyrics(
            sheet_lyrics=sheet_lyrics_history,
            output_dir=OUTPUT_DIR,
        )
        match = check_duplicate(parsed_lyrics, existing, threshold=duplicate_threshold)
        if match:
            console.print(
                f"\n  [red][중복 감지][/red] 유사도 {match.similarity:.0%} "
                f"(기존 {match.matched_id}/{match.matched_source}, '{match.matched_title}')"
            )
            console.print(f"    기존 가사 일부: {match.snippet[:80]}...")
            console.print("  [red][중단][/red] 다른 가사로 시도하거나 --allow-duplicate 사용")
            raise typer.Exit(1)
        console.print(f"\n  [green]중복 없음[/green] (검사 대상 {len(existing)}곡)")

    # 4. 시트에 추가
    new_row = append_pending_row(
        ws,
        title=parsed_title,
        lyrics=parsed_lyrics,
        tags=parsed_tags,
        persona_id=parsed_persona,
        image_prompt=image_prompt,
        thumbnail_path=thumbnail_path,
    )
    console.print(f"\n  [green]시트에 추가 완료[/green] — 행 {new_row}, status=pending")
    console.print(f"  다음 단계: songmaker batch (또는 lint로 미리 점검)")


@app.command(name="retry-failed")
def retry_failed(
    sheet: str = typer.Option("", "--sheet", "-s", help="시트 ID (비우면 config 기본값)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="실제 갱신 없이 대상만 보기"),
) -> None:
    """status=failed 행을 pending으로 되돌려 다음 batch에서 재시도되게 함."""
    from song_maker.sheet import open_sheet
    from song_maker.sheet.client import COL

    config = cfg.load_config()
    sheet_id = sheet or cfg.get(config, "sheets", "default_sheet_id")
    if not sheet_id:
        console.print("[red][에러][/red] --sheet <ID> 또는 config 기본값 필요")
        raise typer.Exit(1)

    sa_path = cfg.get(config, "sheets", "service_account_path") or ""
    worksheet_name = cfg.get(config, "sheets", "worksheet") or None
    try:
        ws = open_sheet(sa_path, sheet_id, worksheet_name)
    except Exception as e:
        console.print(f"[red][에러][/red] 시트 열기 실패: {e}")
        raise typer.Exit(1)

    records = ws.get_all_records()
    targets: list[tuple[int, str, str]] = []  # (row_num, title, error)
    for idx, rec in enumerate(records, start=2):
        st = (rec.get("status") or "").strip().lower()
        if st == "failed":
            targets.append((idx, rec.get("title") or "", rec.get("error") or ""))

    if not targets:
        console.print("  failed 행 없음.")
        return

    console.print(f"\n  failed 행 {len(targets)}개:")
    for row, title, err in targets:
        console.print(f"    행 {row}: {title[:30]} — {err[:60]}")

    if dry_run:
        console.print("\n  --dry-run: 갱신 안 함")
        return

    if not typer.confirm(f"\n  {len(targets)}개를 pending으로 되돌릴까요?", default=True):
        raise typer.Exit(0)

    # batch_update로 한 번에 처리 (시트 API 효율)
    from gspread.utils import rowcol_to_a1

    cells = []
    for row, _, _ in targets:
        cells.append({"range": rowcol_to_a1(row, COL["status"]), "values": [["pending"]]})
        cells.append({"range": rowcol_to_a1(row, COL["error"]), "values": [[""]]})

    ws.batch_update(cells)
    console.print(f"  [green]{len(targets)}개 pending으로 복구 완료[/green]")
    console.print("  다음에 songmaker batch 실행하면 재처리됩니다.")


@app.command()
def credits() -> None:
    """Suno 래퍼의 남은 크레딧을 조회한다 (배치 실행 전 점검용)."""
    from song_maker.creator.suno import get_suno_credits

    config = cfg.load_config()
    info = get_suno_credits(config)
    if info is None:
        console.print("[red][에러][/red] Suno 래퍼에 연결할 수 없습니다.")
        console.print(f"  api_url: {cfg.get(config, 'suno', 'api_url')}")
        console.print("  Docker가 실행 중인지, SUNO_COOKIE가 유효한지 확인하세요.")
        raise typer.Exit(1)

    credits_left = info.get("credits_left", info.get("credits"))
    monthly_limit = info.get("monthly_limit", info.get("limit"))

    console.print(f"\n  [bold]Suno 크레딧[/bold]")
    if credits_left is not None:
        console.print(f"    남은 크레딧: {credits_left}")
        # 1곡당 평균 5 크레딧 가정 (Suno custom_generate 기본)
        if isinstance(credits_left, (int, float)):
            estimated = int(credits_left // 5)
            console.print(f"    추정 가능 곡수: 약 {estimated}곡 (곡당 5 크레딧 가정)")
    if monthly_limit is not None:
        console.print(f"    월 한도: {monthly_limit}")
    console.print(f"\n  raw: {info}")


@app.command()
def timeline(
    folder: str = typer.Argument(..., help="mp3 파일들이 있는 폴더 (예: ~/CapCut/playlist/2030_w19/)"),
    header: str = typer.Option("🎵 Time Track", "--header", help="첫 줄 헤더"),
    output: str = typer.Option("", "--output", "-o", help="결과 저장 파일 경로 (생략 시 stdout)"),
) -> None:
    """플레이리스트용 챕터 타임라인 생성. mp3 폴더 → YouTube 설명용 챕터 텍스트."""
    from pathlib import Path as _Path
    from song_maker.playlist import build_timeline, collect_mp3s

    folder_path = _Path(folder).expanduser()
    if not folder_path.exists() or not folder_path.is_dir():
        console.print(f"[red][에러][/red] 폴더 없음: {folder_path}")
        raise typer.Exit(1)

    mp3s = collect_mp3s(folder_path)
    if not mp3s:
        console.print(f"[red][에러][/red] mp3 파일 없음: {folder_path}")
        raise typer.Exit(1)

    console.print(f"\n  mp3 {len(mp3s)}개 발견 (자연 정렬):")
    for p in mp3s:
        console.print(f"    {p.name}")

    text, entries = build_timeline(mp3s, header=header)
    total = sum(e.duration for e in entries)

    console.print(f"\n  총 재생시간: {int(total // 60)}분 {int(total % 60)}초")
    console.print(f"  {'=' * 60}")
    console.print(text)
    console.print(f"  {'=' * 60}")

    if output:
        out_path = _Path(output).expanduser()
        out_path.write_text(text, encoding="utf-8")
        console.print(f"\n  [green]저장[/green]: {out_path}")


@app.command()
def lint(
    sheet: str = typer.Option("", "--sheet", "-s", help="구글 시트 ID (비우면 config 기본값)"),
    duplicate_threshold: float = typer.Option(0.75, "--duplicate-threshold", help="중복 임계값"),
) -> None:
    """시트의 모든 pending 행을 사전 점검 — 입력 형식, 중복 가사, 배치 내부 중복."""
    from song_maker.sheet import (
        HEADERS,
        fetch_pending_rows,
        open_sheet,
        verify_schema,
    )
    from song_maker.storage import OUTPUT_DIR
    from song_maker.validation import (
        check_duplicate,
        check_duplicate_within_batch,
        lint_row,
        load_existing_lyrics,
    )

    config = cfg.load_config()
    sheet_id = sheet or cfg.get(config, "sheets", "default_sheet_id")
    if not sheet_id:
        console.print("[red][에러][/red] --sheet <ID> 또는 config 기본값 필요")
        raise typer.Exit(1)

    sa_path = cfg.get(config, "sheets", "service_account_path") or ""
    worksheet_name = cfg.get(config, "sheets", "worksheet") or None

    try:
        ws = open_sheet(sa_path, sheet_id, worksheet_name)
    except Exception as e:
        console.print(f"[red][에러][/red] 시트 열기 실패: {e}")
        raise typer.Exit(1)

    ok, schema_issues = verify_schema(ws)
    if not ok:
        console.print("[red][스키마 에러][/red]")
        for i in schema_issues:
            console.print(f"  {i}")
        console.print(f"\n  올바른 헤더: {' | '.join(HEADERS)}")
        raise typer.Exit(1)
    console.print("[green]스키마 OK[/green]")

    rows = fetch_pending_rows(ws)
    console.print(f"\npending 행: {len(rows)}개")

    total_errors = 0
    total_warnings = 0

    # 1. 행별 lint
    for row in rows:
        sheet_row = row["sheet_row"]
        title = (row.get("title") or "")[:40]
        issues = lint_row(row)
        errors = [i for i in issues if i.severity == "error"]
        warns = [i for i in issues if i.severity == "warning"]
        if errors or warns:
            console.print(f"\n행 {sheet_row}: {title}")
            for i in errors:
                console.print(f"  [red]{i}[/red]")
                total_errors += 1
            for i in warns:
                console.print(f"  [yellow]{i}[/yellow]")
                total_warnings += 1

    # 2. 배치 내부 중복
    if rows:
        console.print(f"\n[bold]배치 내부 중복 검사[/bold]")
        candidates = [(str(r["sheet_row"]), r.get("lyrics", "")) for r in rows]
        internal = check_duplicate_within_batch(candidates, threshold=duplicate_threshold)
        if internal:
            for i, j, sim in internal:
                ri, rj = candidates[i][0], candidates[j][0]
                console.print(f"  [red]행 {ri} ↔ 행 {rj}: 유사도 {sim:.0%}[/red]")
                total_errors += 1
        else:
            console.print("  [green]배치 내부 중복 없음[/green]")

    # 3. 기존(done + 로컬) 가사와 중복 검사
    console.print(f"\n[bold]기존 가사 중복 검사[/bold]")
    all_records = ws.get_all_records()
    sheet_lyrics = []
    for idx, rec in enumerate(all_records, start=2):
        st = (rec.get("status") or "").strip().lower()
        if st == "done" and rec.get("lyrics"):
            sheet_lyrics.append((str(idx), rec.get("title") or "", rec["lyrics"]))
    existing = load_existing_lyrics(sheet_lyrics=sheet_lyrics, output_dir=OUTPUT_DIR)
    console.print(f"  기존 가사 풀: {len(existing)}곡")

    for row in rows:
        sheet_row = row["sheet_row"]
        match = check_duplicate(row.get("lyrics", ""), existing, threshold=duplicate_threshold)
        if match:
            console.print(
                f"  [red]행 {sheet_row} ↔ 기존 {match.matched_id} ({match.matched_source}): "
                f"유사도 {match.similarity:.0%}[/red]"
            )
            total_errors += 1

    # 결과 요약
    console.print(f"\n{'=' * 60}")
    if total_errors:
        console.print(f"[red][결과][/red] 에러 {total_errors}건, 경고 {total_warnings}건")
        raise typer.Exit(1)
    else:
        console.print(f"[green][결과][/green] 에러 없음, 경고 {total_warnings}건 — batch 진행 가능")


@app.command()
def direct(
    title: str = typer.Option(..., "--title", "-t", help="곡 제목 (Suno)"),
    lyrics_file: str = typer.Option(..., "--lyrics-file", "-l", help="가사 파일 경로 (txt, 섹션 마커 권장)"),
    tags: str = typer.Option(..., "--tags", help="Suno tags (예: \"95 BPM, Modern Pop, Female vocal, nostalgic\")"),
    persona_id: str = typer.Option("", "--persona-id", help="Suno persona UUID (선택)"),
    image_prompt: str = typer.Option("", "--image-prompt", help="배경 이미지 프롬프트 (선택, 빈 값이면 자동 생성)"),
    external_thumbnail: str = typer.Option("", "--thumbnail", help="외부 썸네일 PNG 경로 (시니어 채널 등)"),
    project: str = typer.Option("", "--project", "-p", help="프로젝트 이름"),
    skip_image: bool = typer.Option(False, "--skip-image", help="Gemini 이미지 생성 건너뛰기 (가사/곡만 빠르게 검증)"),
    skip_duplicate_check: bool = typer.Option(False, "--allow-duplicate", help="중복 가사 검사 건너뛰기"),
    duplicate_threshold: float = typer.Option(0.75, "--duplicate-threshold", help="중복 차단 임계값 (0~1)"),
) -> None:
    """[Phase 0] 1곡 단발 생성 — 캘리브레이션용. 시트/업로드 안 거치고 바로 Suno→이미지→CapCut 핸드오프."""
    from pathlib import Path as _Path

    from song_maker.capcut import capcut_paths, handoff_song
    from song_maker.creator.suno import generate_song_direct, verify_gate3
    from song_maker.gates import run_gate
    from song_maker.imager.gemini import generate_images, verify_gate4
    from song_maker.models import SongRequest
    from song_maker.storage import (
        OUTPUT_DIR,
        create_song,
        generate_project_name,
        get_song_dir,
        save_project_meta,
        save_song_meta,
    )
    from song_maker.validation import (
        check_duplicate,
        lint_song_request,
        load_existing_lyrics,
    )

    config = cfg.load_config()

    # 가사 파일 로드
    lyrics_path = _Path(lyrics_file).expanduser()
    if not lyrics_path.exists():
        console.print(f"[red][에러][/red] 가사 파일 없음: {lyrics_path}")
        raise typer.Exit(1)
    lyrics_text = lyrics_path.read_text(encoding="utf-8").strip()

    request = SongRequest(
        genre="", mood="", theme=title[:50],
        suno_title=title,
        suno_lyrics=lyrics_text,
        suno_tags=tags,
        suno_persona_id=persona_id or None,
        custom_image_prompt=image_prompt or None,
    )

    # 1. lint 사전검사
    console.print("\n  [bold]사전 검증[/bold]")
    issues = lint_song_request(request)
    has_error = any(i.severity == "error" for i in issues)
    for i in issues:
        color = "red" if i.severity == "error" else "yellow"
        console.print(f"  [{color}]{i}[/{color}]")
    if has_error:
        console.print("[red][중단][/red] 입력 에러 — 수정 후 다시 시도하세요.")
        raise typer.Exit(1)
    if not issues:
        console.print("  [green]lint OK[/green]")

    # 2. 중복 가사 검사
    if not skip_duplicate_check:
        console.print("\n  [bold]중복 가사 검사[/bold]")
        existing = load_existing_lyrics(output_dir=OUTPUT_DIR)
        match = check_duplicate(lyrics_text, existing, threshold=duplicate_threshold)
        if match:
            console.print(
                f"  [red][중복 감지][/red] 유사도 {match.similarity:.0%} "
                f"(기존 곡 {match.matched_id}, 출처 {match.matched_source})"
            )
            console.print(f"  기존 가사 일부: {match.snippet[:80]}...")
            console.print("  [red][중단][/red] 다른 가사로 시도하거나 --allow-duplicate 사용")
            raise typer.Exit(1)
        console.print(f"  [green]중복 없음[/green] (검사 대상 {len(existing)}곡)")

    # 3. 곡 생성
    project_name = project or generate_project_name()
    song = create_song(project_name, request)
    song.suno_title = request.suno_title
    song.suno_lyrics = request.suno_lyrics
    song.suno_tags = request.suno_tags
    song.suno_persona_id = request.suno_persona_id
    song.custom_image_prompt = request.custom_image_prompt
    song_dir = get_song_dir(project_name, song.id)

    console.print(f"\n  [bold]Stage 3: Suno (direct)[/bold] (ID: {song.id})")
    try:
        song = generate_song_direct(config, song, song_dir)
        save_song_meta(project_name, song)
        console.print(f"  [green]오디오[/green]: {song.audio_path}")
    except Exception as e:
        console.print(f"  [red][실패][/red] Suno: {e}")
        raise typer.Exit(1)

    gate3 = verify_gate3(song, song_dir)
    song.gates["gate3"] = gate3.to_dict()
    if not run_gate(gate3, "곡 생성"):
        save_song_meta(project_name, song)
        raise typer.Exit(1)
    save_song_meta(project_name, song)

    # 4. 이미지 (스킵 가능)
    external_thumb_path = None
    if external_thumbnail:
        external_thumb_path = _Path(external_thumbnail).expanduser()
        if not external_thumb_path.exists():
            console.print(f"  [yellow][경고][/yellow] 외부 썸네일 파일 없음: {external_thumb_path}")
            external_thumb_path = None

    if not skip_image:
        gemini_key = cfg.get(config, "gemini", "api_key")
        if gemini_key:
            console.print(f"\n  [bold]Stage 4: 이미지[/bold]")
            try:
                song = generate_images(config, song, song_dir)
                save_song_meta(project_name, song)
                console.print(f"  [green]배경[/green]: {song.background_path}")
                console.print(f"  [green]썸네일[/green]: {song.thumbnail_path}")
                gate4 = verify_gate4(song, song_dir)
                song.gates["gate4"] = gate4.to_dict()
                run_gate(gate4, "이미지 생성")
                save_song_meta(project_name, song)
            except Exception as e:
                console.print(f"  [yellow][경고][/yellow] 이미지 생성 실패: {e}")
        else:
            console.print("  [yellow][경고][/yellow] Gemini 키 미설정 — 이미지 건너뜀")

    # 5. CapCut 핸드오프
    paths = capcut_paths(config)
    inbox = handoff_song(song, song_dir, paths, external_thumbnail=external_thumb_path)

    save_project_meta(project_name, [song.id])

    console.print(f"\n  {'=' * 60}")
    console.print(f"  [bold]완료![/bold]")
    console.print(f"  song_id: {song.id}")
    console.print(f"  로컬 작업: {song_dir}")
    console.print(f"  [bold]CapCut inbox[/bold]: {inbox}")
    console.print(f"  {'=' * 60}")
    console.print(f"\n  다음 단계:")
    console.print(f"    1. CapCut 열기 → import {inbox}/")
    console.print(f"    2. 편집 → export → {paths.outbox_root}/{song.id}.mp4")
    console.print(f"    3. songmaker upload-capcut {song.id}")


@app.command()
def batch(
    sheet: str = typer.Option("", "--sheet", "-s", help="구글 시트 ID (URL의 /d/<ID>/edit). 비우면 config 기본값."),
    project: str = typer.Option("", "--project", "-p", help="프로젝트 이름"),
    limit: int = typer.Option(0, "--limit", "-n", help="처리할 행 수 제한 (0=전부)"),
    skip_image: bool = typer.Option(False, "--skip-image", help="Gemini 이미지 생성 건너뛰기"),
    skip_duplicate_check: bool = typer.Option(False, "--allow-duplicate", help="중복 가사 검사 건너뛰기"),
    duplicate_threshold: float = typer.Option(0.75, "--duplicate-threshold", help="중복 차단 임계값 (0~1)"),
) -> None:
    """[Phase 1] 구글 시트 pending 행을 일괄 처리 — Suno→이미지→CapCut inbox 핸드오프.

    렌더/업로드는 별도 (CapCut 편집 후 songmaker upload-capcut).
    중복 가사 자동 차단 (75% 이상 유사 시 status=failed).
    """
    from pathlib import Path as _Path

    from song_maker.capcut import capcut_paths, handoff_song
    from song_maker.creator.suno import generate_song_direct, verify_gate3
    from song_maker.gates import run_gate
    from song_maker.imager.gemini import generate_images, verify_gate4
    from song_maker.sheet import (
        HEADERS,
        fetch_pending_rows,
        mark_done,
        mark_failed,
        mark_processing,
        open_sheet,
        row_external_thumbnail,
        row_to_song_request,
        verify_schema,
    )
    from song_maker.storage import (
        OUTPUT_DIR,
        create_song,
        generate_project_name,
        get_song_dir,
        save_project_meta,
        save_song_meta,
    )
    from song_maker.validation import (
        check_duplicate,
        check_duplicate_within_batch,
        lint_song_request,
        load_existing_lyrics,
    )

    config = cfg.load_config()
    sheet_id = sheet or cfg.get(config, "sheets", "default_sheet_id")
    if not sheet_id:
        console.print("[red][에러][/red] 시트 ID 필요. --sheet <ID> 또는 config [sheets] default_sheet_id")
        raise typer.Exit(1)

    sa_path = cfg.get(config, "sheets", "service_account_path") or ""
    worksheet_name = cfg.get(config, "sheets", "worksheet") or None

    console.print(f"\n  [bold]시트 연결[/bold]: {sheet_id[:20]}...")
    try:
        ws = open_sheet(sa_path, sheet_id, worksheet_name)
    except FileNotFoundError as e:
        console.print(f"[red][에러][/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red][에러][/red] 시트 열기 실패: {e}")
        raise typer.Exit(1)

    ok, schema_issues = verify_schema(ws)
    if not ok:
        console.print("[red][에러][/red] 시트 헤더 스키마 불일치:")
        for i in schema_issues:
            console.print(f"    {i}")
        console.print(f"\n  올바른 헤더: {' | '.join(HEADERS)}")
        raise typer.Exit(1)

    rows = fetch_pending_rows(ws)
    if limit > 0:
        rows = rows[:limit]

    if not rows:
        console.print("  처리할 pending 행이 없습니다.")
        return

    console.print(f"  pending 행: {len(rows)}개")

    # Suno 크레딧 사전 점검
    from song_maker.creator.suno import get_suno_credits
    credits_info = get_suno_credits(config)
    if credits_info is None:
        console.print("  [yellow][경고][/yellow] Suno 래퍼 연결 실패 — credits 점검 건너뜀 (직접 실행 시 실패할 수 있음)")
    else:
        left = credits_info.get("credits_left", credits_info.get("credits", 0))
        if isinstance(left, (int, float)):
            estimated_cost = len(rows) * 5  # 곡당 5 크레딧 추정
            if left < estimated_cost:
                console.print(
                    f"  [red][경고][/red] Suno 크레딧 부족 가능: 남은 {left}, 예상 필요 {estimated_cost} ({len(rows)}곡 × 5)"
                )
                if not typer.confirm("  그래도 계속 진행하시겠습니까?", default=False):
                    raise typer.Exit(0)
            else:
                console.print(f"  [cyan]Suno 크레딧[/cyan]: {left} (예상 사용 ~{estimated_cost})")

    # 사전 검사 1: 배치 내부 중복
    if not skip_duplicate_check:
        candidates = [(str(r["sheet_row"]), r.get("lyrics", "")) for r in rows]
        internal = check_duplicate_within_batch(candidates, threshold=duplicate_threshold)
        if internal:
            console.print(f"\n  [yellow][경고][/yellow] 배치 내부 중복 가사 {len(internal)}쌍:")
            for i, j, sim in internal:
                ri, rj = candidates[i][0], candidates[j][0]
                console.print(f"    행 {ri} ↔ 행 {rj} (유사도 {sim:.0%})")
            console.print("  처리는 진행하되 두 번째 행에서 중복 차단됨")

    # 사전 검사 2: 기존 가사 로드 (시트 done + 로컬)
    existing_lyrics = []
    if not skip_duplicate_check:
        all_records = ws.get_all_records()
        sheet_lyrics = []
        for idx, rec in enumerate(all_records, start=2):
            status = (rec.get("status") or "").strip().lower()
            lyrics = rec.get("lyrics") or ""
            if status == "done" and lyrics:
                sheet_lyrics.append((str(idx), rec.get("title") or "", lyrics))
        existing_lyrics = load_existing_lyrics(
            sheet_lyrics=sheet_lyrics,
            output_dir=OUTPUT_DIR,
        )
        console.print(f"  기존 가사 로드: {len(existing_lyrics)}곡")

    project_name = project or generate_project_name()
    paths = capcut_paths(config)
    song_ids: list[str] = []
    summary = {"done": 0, "failed": 0, "duplicate": 0}

    # Drive 아카이브 준비 (선택)
    drive_svc = None
    drive_parent_id = ""
    if cfg.get(config, "drive", "archive_enabled") in (True, "true", "True", "1"):
        drive_parent_id = cfg.get(config, "drive", "lyrics_parent_folder_id") or ""
        if drive_parent_id:
            try:
                from song_maker.drive import archive_lyrics, open_drive
                drive_svc = open_drive(sa_path)
                console.print("  [cyan]Drive 아카이브 활성화[/cyan]")
            except Exception as e:
                console.print(f"  [yellow][경고][/yellow] Drive 초기화 실패: {e}")
                drive_svc = None

    for i, row in enumerate(rows, 1):
        sheet_row = row["sheet_row"]
        title_preview = (row.get("title") or "")[:30]
        console.print(f"\n  {'=' * 60}")
        console.print(f"  [{i}/{len(rows)}] 행 {sheet_row}: {title_preview}")
        console.print(f"  {'=' * 60}")

        try:
            mark_processing(ws, sheet_row)
        except Exception as e:
            console.print(f"  [red][에러][/red] 시트 갱신 실패: {e}")
            continue

        try:
            request = row_to_song_request(row)

            # lint 검사
            lint_issues = lint_song_request(request)
            errors = [i for i in lint_issues if i.severity == "error"]
            if errors:
                err = "; ".join(str(e) for e in errors)
                raise RuntimeError(f"lint 에러: {err}")
            for w in lint_issues:
                if w.severity == "warning":
                    console.print(f"  [yellow]{w}[/yellow]")

            # 중복 검사
            if not skip_duplicate_check:
                match = check_duplicate(
                    request.suno_lyrics or "",
                    existing_lyrics,
                    threshold=duplicate_threshold,
                )
                if match:
                    summary["duplicate"] += 1
                    raise RuntimeError(
                        f"중복 가사 ({match.similarity:.0%} 유사, 기존 곡 {match.matched_id}/{match.matched_source})"
                    )

            song = create_song(project_name, request)
            song.suno_title = request.suno_title
            song.suno_lyrics = request.suno_lyrics
            song.suno_tags = request.suno_tags
            song.suno_persona_id = request.suno_persona_id
            song.custom_image_prompt = request.custom_image_prompt
            song.sheet_row = sheet_row
            song_ids.append(song.id)
            song_dir = get_song_dir(project_name, song.id)

            # Stage 3: Suno direct
            console.print(f"\n  [bold]Stage 3: Suno[/bold] (ID: {song.id})")
            song = generate_song_direct(config, song, song_dir)
            save_song_meta(project_name, song)

            gate3 = verify_gate3(song, song_dir)
            song.gates["gate3"] = gate3.to_dict()
            if not gate3.passed:
                fails = ", ".join(c.message for c in gate3.failures)
                raise RuntimeError(f"Gate3 실패: {fails}")
            save_song_meta(project_name, song)

            # Stage 4: 이미지 (스킵 가능)
            external_thumb = None
            ext_thumb_str = row_external_thumbnail(row)
            if ext_thumb_str:
                ext_path = _Path(ext_thumb_str).expanduser()
                if ext_path.exists():
                    external_thumb = ext_path
                    console.print(f"  [cyan]외부 썸네일 사용[/cyan]: {ext_path.name}")
                else:
                    console.print(f"  [yellow][경고][/yellow] 외부 썸네일 파일 없음: {ext_path}")

            if not skip_image:
                gemini_key = cfg.get(config, "gemini", "api_key")
                if gemini_key:
                    console.print(f"\n  [bold]Stage 4: Gemini 이미지[/bold]")
                    try:
                        song = generate_images(config, song, song_dir)
                        gate4 = verify_gate4(song, song_dir)
                        song.gates["gate4"] = gate4.to_dict()
                        save_song_meta(project_name, song)
                    except Exception as e:
                        console.print(f"  [yellow][경고][/yellow] 이미지 실패: {e}")
                else:
                    console.print("  [yellow][경고][/yellow] Gemini 키 미설정")

            # CapCut 핸드오프
            inbox = handoff_song(song, song_dir, paths, external_thumbnail=external_thumb)
            console.print(f"  [green]CapCut inbox[/green]: {inbox}")

            # Drive 아카이브 (선택)
            if drive_svc and drive_parent_id:
                try:
                    file_id = archive_lyrics(
                        drive_svc,
                        drive_parent_id,
                        song_id=song.id,
                        title=song.suno_title or "",
                        lyrics=song.suno_lyrics or "",
                    )
                    console.print(f"  [cyan]Drive 아카이브[/cyan]: file_id={file_id[:12]}...")
                except Exception as e:
                    console.print(f"  [yellow][경고][/yellow] Drive 아카이브 실패: {e}")

            # 시트 갱신: status=awaiting_capcut (CapCut 편집 대기)
            mark_done(
                ws,
                sheet_row,
                song_id=song.id,
                audio_url=song.suno_audio_url or "",
                youtube_url="",
            )
            summary["done"] += 1

        except Exception as e:
            err_msg = f"{type(e).__name__}: {e}"
            console.print(f"  [red][실패][/red] {err_msg}")
            try:
                mark_failed(ws, sheet_row, err_msg)
            except Exception as e2:
                console.print(f"  [red]시트 갱신 실패[/red]: {e2}")
            summary["failed"] += 1

    save_project_meta(project_name, song_ids)

    console.print(f"\n  {'=' * 60}")
    console.print(f"  [bold]배치 완료[/bold]")
    console.print(f"    성공: {summary['done']}곡")
    console.print(f"    실패: {summary['failed']}곡 (중복: {summary['duplicate']}곡 포함)")
    console.print(f"    프로젝트: {project_name}")
    console.print(f"    CapCut inbox: {paths.inbox_root}")
    console.print(f"  {'=' * 60}")
    console.print(f"\n  다음 단계:")
    console.print(f"    1. CapCut 열어서 각 곡 편집 (mp3+이미지 import, 제목 추가, 음파/전환)")
    console.print(f"    2. export → {paths.outbox_root}/<song_id>.mp4")
    console.print(f"    3. songmaker upload-capcut <song_id> (또는 --all)")


@app.command(name="upload-capcut")
def upload_capcut(
    song_id: str = typer.Argument("", help="업로드할 song_id (--all/--playlist 시 무시)"),
    all_pending: bool = typer.Option(False, "--all", help="outbox의 모든 mp4 일괄 업로드 (개별 곡)"),
    playlist_mp4: str = typer.Option("", "--playlist", help="플레이리스트 mp4 (1시간 mix). --songs-dir 필수"),
    songs_dir: str = typer.Option("", "--songs-dir", help="플레이리스트 mp3 폴더 (타임라인 생성용)"),
    playlist_title: str = typer.Option("", "--playlist-title", help="플레이리스트 영상 YouTube 제목"),
    playlist_desc: str = typer.Option("", "--playlist-desc", help="플레이리스트 본문 (타임라인은 자동 prepend)"),
    translate: bool = typer.Option(False, "--translate", help="제목/본문을 50개국어로 자동 번역하여 localizations 적용"),
    playlist_thumbnail: str = typer.Option("", "--thumbnail", help="플레이리스트 썸네일 PNG 경로"),
    sheet: str = typer.Option("", "--sheet", "-s", help="시트 ID (시트 갱신용, 비우면 config 기본값)"),
    privacy: str = typer.Option("private", "--privacy", help="YouTube 공개 설정 (private/unlisted/public)"),
    mp4_path: str = typer.Option("", "--mp4", help="명시적 mp4 경로 (song_id 자동 매칭 안 될 때)"),
) -> None:
    """[Phase 1 마지막] CapCut export mp4를 YouTube에 비공개 업로드.

    3가지 모드:
      1) song_id 단일: songmaker upload-capcut <song_id>
      2) 일괄 (개별 곡): songmaker upload-capcut --all
      3) 플레이리스트 mix: songmaker upload-capcut --playlist <mp4> --songs-dir <folder>
    """
    from pathlib import Path as _Path

    from song_maker.capcut import capcut_paths
    from song_maker.playlist import build_timeline, collect_mp3s
    from song_maker.uploader.youtube import upload_capcut as do_upload_capcut
    from song_maker.sheet import (
        mark_done,
        mark_failed,
        open_sheet,
    )

    config = cfg.load_config()
    paths = capcut_paths(config)

    # 모드 1: 플레이리스트
    if playlist_mp4:
        mp4 = _Path(playlist_mp4).expanduser()
        if not mp4.exists():
            console.print(f"[red][에러][/red] mp4 없음: {mp4}")
            raise typer.Exit(1)
        if not songs_dir:
            console.print("[red][에러][/red] --playlist 사용 시 --songs-dir 필수 (타임라인 생성용)")
            raise typer.Exit(1)
        songs_path = _Path(songs_dir).expanduser()
        if not songs_path.is_dir():
            console.print(f"[red][에러][/red] songs-dir 폴더 없음: {songs_path}")
            raise typer.Exit(1)

        mp3s = collect_mp3s(songs_path)
        if not mp3s:
            console.print(f"[red][에러][/red] {songs_path}에 mp3 없음")
            raise typer.Exit(1)

        console.print(f"\n  플레이리스트 모드 — mp3 {len(mp3s)}개")
        timeline_text, entries = build_timeline(mp3s)
        for e in entries:
            console.print(f"    {e.line()}")

        title = playlist_title or mp4.stem
        description = (
            timeline_text + "\n\n" + (playlist_desc or "")
        ).strip()

        meta = {
            "youtube_title": title[:100],
            "youtube_description": description[:5000],
            "youtube_tags": [],
            "timeline": [],  # 이미 description에 prepend
        }

        # 다국어 번역 (선택)
        if translate:
            gemini_key = cfg.get(config, "gemini", "api_key")
            if not gemini_key:
                console.print("  [yellow][경고][/yellow] Gemini 키 미설정 — 번역 건너뜀")
            else:
                console.print(f"\n  [bold]50개국어 번역 중[/bold] (Gemini)")
                try:
                    from song_maker.translator import (
                        translate_metadata,
                        to_youtube_localizations,
                    )
                    text_model = cfg.get(config, "gemini", "text_model") or "gemini-3-flash-preview"
                    text_fallback = cfg.get(config, "gemini", "text_fallback_model") or "gemini-2.5-flash"
                    results = translate_metadata(
                        title=title,
                        description=description,
                        api_key=gemini_key,
                        model=text_model,
                        fallback_model=text_fallback,
                    )
                    localizations = to_youtube_localizations(results)
                    meta["localizations"] = localizations
                    console.print(f"  [green]번역 완료[/green]: {len(localizations)}개 언어")
                except Exception as e:
                    console.print(f"  [yellow][경고][/yellow] 번역 실패 (원본 언어로 업로드): {e}")

        # 썸네일
        thumb = None
        if playlist_thumbnail:
            tp = _Path(playlist_thumbnail).expanduser()
            if tp.exists():
                thumb = tp

        try:
            url = do_upload_capcut(
                mp4_path=mp4,
                meta=meta,
                privacy=privacy,
                thumbnail_path=thumb,
            )
            console.print(f"\n  [green]플레이리스트 업로드 완료[/green]: {url}")
        except Exception as e:
            console.print(f"  [red][실패][/red] {type(e).__name__}: {e}")
            raise typer.Exit(1)
        return

    # 모드 2/3: 개별 곡 (단일 또는 --all)
    targets: list[tuple[str, _Path]] = []  # (song_id, mp4_path)

    if all_pending:
        if not paths.outbox_root.exists():
            console.print(f"[red][에러][/red] outbox 폴더 없음: {paths.outbox_root}")
            raise typer.Exit(1)
        for mp4 in sorted(paths.outbox_root.glob("*.mp4")):
            sid = mp4.stem.split("_")[0]  # 첫 _ 앞을 song_id로 추정
            targets.append((sid, mp4))
        if not targets:
            console.print(f"  outbox에 mp4 파일 없음: {paths.outbox_root}")
            return
    elif mp4_path:
        p = _Path(mp4_path).expanduser()
        if not p.exists():
            console.print(f"[red][에러][/red] mp4 파일 없음: {p}")
            raise typer.Exit(1)
        sid = song_id or p.stem.split("_")[0]
        targets.append((sid, p))
    elif song_id:
        mp4 = paths.find_outbox_mp4(song_id)
        if not mp4:
            console.print(f"[red][에러][/red] outbox에서 song_id={song_id} 매칭 mp4 못 찾음: {paths.outbox_root}")
            raise typer.Exit(1)
        targets.append((song_id, mp4))
    else:
        console.print("[red][에러][/red] song_id 또는 --all 또는 --mp4 중 하나 필요")
        raise typer.Exit(1)

    # 시트 연결 (선택)
    ws = None
    sheet_id = sheet or cfg.get(config, "sheets", "default_sheet_id")
    if sheet_id:
        sa_path = cfg.get(config, "sheets", "service_account_path") or ""
        worksheet_name = cfg.get(config, "sheets", "worksheet") or None
        try:
            ws = open_sheet(sa_path, sheet_id, worksheet_name)
        except Exception as e:
            console.print(f"  [yellow][경고][/yellow] 시트 연결 실패 (시트 갱신 생략): {e}")
            ws = None

    summary = {"done": 0, "failed": 0}

    for i, (sid, mp4) in enumerate(targets, 1):
        console.print(f"\n  {'=' * 60}")
        console.print(f"  [{i}/{len(targets)}] {sid} → {mp4.name}")
        console.print(f"  {'=' * 60}")

        # inbox에서 youtube_meta.json 찾기
        meta_path = paths.song_inbox(sid) / "youtube_meta.json"
        meta = {}
        if meta_path.exists():
            import json as _json
            try:
                meta = _json.loads(meta_path.read_text(encoding="utf-8"))
                console.print(f"  [cyan]meta 로드[/cyan]: {meta.get('youtube_title', sid)}")
            except Exception as e:
                console.print(f"  [yellow][경고][/yellow] meta 파싱 실패: {e}")
        else:
            console.print(f"  [yellow][경고][/yellow] youtube_meta.json 없음 — 기본값 사용")

        # 썸네일
        thumb_path = paths.song_inbox(sid) / "thumbnail.png"
        thumb = thumb_path if thumb_path.exists() else None

        try:
            youtube_url = do_upload_capcut(
                mp4_path=mp4,
                meta=meta,
                privacy=privacy,
                thumbnail_path=thumb,
            )
            console.print(f"  [green]업로드 완료[/green] ({privacy}): {youtube_url}")

            # 시트 갱신 (sheet_row를 meta에서 못 가져오면 song_id로 검색 — 단순화: meta.song_id만 사용)
            if ws and meta.get("sheet_row"):
                try:
                    mark_done(
                        ws,
                        meta["sheet_row"],
                        song_id=sid,
                        audio_url=meta.get("suno_audio_url", ""),
                        youtube_url=youtube_url,
                    )
                except Exception as e:
                    console.print(f"  [yellow]시트 갱신 실패[/yellow]: {e}")

            summary["done"] += 1
        except Exception as e:
            err_msg = f"{type(e).__name__}: {e}"
            console.print(f"  [red][실패][/red] {err_msg}")
            summary["failed"] += 1

    console.print(f"\n  {'=' * 60}")
    console.print(f"  [bold]업로드 완료[/bold] — done: {summary['done']}, failed: {summary['failed']}")
    console.print(f"  {'=' * 60}")


@app.command()
def list_songs() -> None:
    """생성된 곡 목록을 표시합니다."""
    from song_maker.storage import list_all_songs

    songs = list_all_songs()
    if not songs:
        console.print("  생성된 곡이 없습니다.")
        return

    table = Table(title="곡 목록")
    table.add_column("ID", width=10)
    table.add_column("주제", width=15)
    table.add_column("장르", width=10)
    table.add_column("상태", width=10)
    table.add_column("프로젝트", width=20)
    table.add_column("생성일", width=18)

    for project_name, song in songs:
        created = song.created_at.strftime("%Y-%m-%d %H:%M") if song.created_at else "-"
        table.add_row(
            song.id,
            song.theme[:15] if song.theme else "-",
            song.genre,
            song.status,
            project_name,
            created,
        )

    console.print(table)


@app.command()
def config(
    show: bool = typer.Option(False, "--show", help="현재 설정 표시"),
) -> None:
    """API 키를 설정합니다."""
    current = cfg.load_config()

    if show:
        table = Table(title="현재 설정")
        table.add_column("항목", width=25)
        table.add_column("값", width=40)

        table.add_row("YouTube API Key", cfg.mask_key(cfg.get(current, "youtube", "api_key")))
        table.add_row("YouTube Region", cfg.get(current, "youtube", "default_region"))
        table.add_row("Gemini API Key", cfg.mask_key(cfg.get(current, "gemini", "api_key")))
        table.add_row("Gemini Model", cfg.get(current, "gemini", "model"))
        table.add_row("Suno API URL", cfg.get(current, "suno", "api_url"))
        table.add_row("Suno Provider", cfg.get(current, "suno", "provider"))
        table.add_row("Suno Cookie", cfg.mask_key(cfg.get(current, "suno", "cookie")))
        table.add_row("2Captcha Key", cfg.mask_key(cfg.get(current, "suno", "twocaptcha_key")))
        table.add_row("해상도", cfg.get(current, "render", "resolution"))
        table.add_row("기본 공개 설정", cfg.get(current, "upload", "default_privacy"))

        console.print(table)
        return

    # 대화형 설정
    console.print("\n  API 키 설정\n")

    youtube_key = typer.prompt(
        "  YouTube API Key",
        default=cfg.get(current, "youtube", "api_key") or "",
        show_default=False,
    )
    gemini_key = typer.prompt(
        "  Gemini API Key",
        default=cfg.get(current, "gemini", "api_key") or "",
        show_default=False,
    )
    suno_url = typer.prompt(
        "  Suno API URL",
        default=cfg.get(current, "suno", "api_url"),
    )

    current["youtube"]["api_key"] = youtube_key
    current["gemini"]["api_key"] = gemini_key
    current["suno"]["api_url"] = suno_url

    cfg.save_config(current)
    console.print(f"\n  [green]설정 저장 완료[/green]: {cfg.CONFIG_PATH}")


# ========== 페르소나 메이크 자동화 워크플로우 명령 ==========

@app.command()
def transform(
    title: str = typer.Option(..., "--title", "-t", help="새 영어 제목 (페르소나 시트 C열)"),
    subject: str = typer.Option(..., "--subject", "-s", help="새 가사 내용 한국어 설명 (E열)"),
    lyrics_file: Optional[str] = typer.Option(
        None, "--lyrics-file", "-f", help="원곡 가사 파일 경로 (페르소나 시트 G열)"
    ),
    lyrics: Optional[str] = typer.Option(
        None, "--lyrics", "-l", help="원곡 가사 텍스트 직접 입력 (--lyrics-file과 둘 중 하나)"
    ),
    out: Optional[str] = typer.Option(
        None, "--out", "-o", help="출력 파일 (미지정 시 stdout)"
    ),
) -> None:
    """원곡 가사를 5규칙(음절수·다른 단어·'/' 유지·발라드 감성·저작권 안전)으로 변환.

    Gemini 텍스트 모델 사용. 페르소나 메이크 자동화 시트의 G열(원가사) →
    C(영문 제목) + E(내용) 기반으로 → J열(새 가사) 생성용.
    """
    from pathlib import Path

    from song_maker.transform.lyric import transform_lyrics

    config = cfg.load_config()

    # 원가사 로드
    if lyrics_file:
        original = Path(lyrics_file).read_text(encoding="utf-8").strip()
    elif lyrics:
        original = lyrics.strip()
    else:
        console.print("  [red][에러][/red] --lyrics-file 또는 --lyrics 중 하나는 필요합니다.")
        raise typer.Exit(1)

    if not original:
        console.print("  [red][에러][/red] 원가사가 비어있습니다.")
        raise typer.Exit(1)

    console.print(f"  원가사: {len(original)}자")
    console.print(f"  새 제목: {title}")
    console.print(f"  내용: {subject}")
    console.print(f"  Gemini 호출 중... (모델: {cfg.get(config, 'gemini', 'text_model')})\n")

    try:
        new_lyrics = transform_lyrics(config, original, title, subject)
    except Exception as e:
        console.print(f"  [red][에러][/red] {e}")
        raise typer.Exit(1)

    if out:
        out_path = Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(new_lyrics, encoding="utf-8")
        console.print(f"  [green][저장][/green] {out_path} ({len(new_lyrics)}자)")
    else:
        console.print("  [green][결과][/green]")
        console.print(new_lyrics)


@app.command(name="transform-batch")
def transform_batch_cmd(
    sheet: Optional[str] = typer.Option(None, "--sheet", help="시트 ID 오버라이드"),
    dry_run: bool = typer.Option(False, "--dry-run", help="시트에 안 쓰고 결과만 표시"),
) -> None:
    """페르소나 시트에서 G(원가사) 있고 J(새가사) 비어있는 행을 일괄 변환.

    각 행에 대해:
      G + Title1 + Subject → 5규칙 변환 → J(Song Lyric) 갱신
    Status는 변경하지 않음 (B열은 사용자가 'DO IT'으로 트리거).
    """
    from song_maker.sheet.client import open_sheet
    from song_maker.sheet.persona_client import (
        fetch_persona_needs_transform,
        verify_persona_schema,
        write_transformed_lyric,
    )
    from song_maker.transform.lyric import transform_lyrics

    config = cfg.load_config()
    sa_path = cfg.get(config, "sheets", "service_account_path")
    sheet_id = sheet or cfg.get(config, "sheets", "default_sheet_id")
    worksheet = cfg.get(config, "sheets", "worksheet") or None

    if not sheet_id:
        console.print("  [red][에러][/red] 시트 ID 미설정. --sheet 또는 config 등록 필요.")
        raise typer.Exit(1)

    ws = open_sheet(sa_path, sheet_id, worksheet)
    ok, issues = verify_persona_schema(ws)
    if not ok:
        console.print("  [yellow]시트 헤더가 페르소나 메이크 자동화 스키마와 다름:[/yellow]")
        for i in issues:
            console.print(f"    {i}")
        console.print("  계속 진행은 위험합니다. 헤더 정렬 후 다시 시도하세요.")
        raise typer.Exit(1)

    rows = fetch_persona_needs_transform(ws)
    console.print(f"  변환 대상 행: {len(rows)}")
    if not rows:
        console.print("  [dim]변환할 행 없음 (G있고 J비어있는 행이 0건).[/dim]")
        return

    for r in rows:
        sheet_row = r["sheet_row"]
        title = r.get("Title1", "")
        subject = r.get("Subject", "")
        original = r.get("Original Lyric", "")
        console.print(f"\n  [row {sheet_row}] {title}")
        try:
            new = transform_lyrics(config, original, title, subject)
            console.print(f"    변환 완료 ({len(new)}자)")
            if dry_run:
                console.print(f"    [dim]dry-run: 시트 미반영[/dim]")
            else:
                write_transformed_lyric(ws, sheet_row, new)
                console.print(f"    [green]J열 갱신 완료[/green]")
        except Exception as e:
            console.print(f"    [red][실패][/red] {e}")


@app.command(name="batch-persona")
def batch_persona_cmd(
    sheet: Optional[str] = typer.Option(None, "--sheet", help="시트 ID 오버라이드"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="프로젝트 이름"),
    skip_image: bool = typer.Option(False, "--skip-image", help="이미지 생성 스킵"),
) -> None:
    """페르소나 메이크 자동화 시트의 트리거된 행을 Suno로 일괄 처리.

    조건: Status가 비어있거나 'DO IT'/'pending'/'ready'면서 Song Lyric(J)이 채워진 행.
    각 행: Suno custom_generate → audio.mp3 다운로드 → Gemini 썸네일 → Music URL(K)에 audio_url 기록.
    """
    from song_maker.creator.suno import generate_song_direct, verify_gate3
    from song_maker.imager.gemini import generate_images, verify_gate4
    from song_maker.sheet.client import open_sheet
    from song_maker.sheet.persona_client import (
        fetch_persona_pending,
        mark_persona_done,
        mark_persona_failed,
        mark_persona_processing,
        row_to_persona_song_request,
        verify_persona_schema,
    )
    from song_maker.storage import (
        create_song,
        generate_project_name,
        get_song_dir,
        save_song_meta,
    )
    from song_maker.gates import run_gate

    config = cfg.load_config()
    sa_path = cfg.get(config, "sheets", "service_account_path")
    sheet_id = sheet or cfg.get(config, "sheets", "default_sheet_id")
    worksheet = cfg.get(config, "sheets", "worksheet") or None

    if not sheet_id:
        console.print("  [red][에러][/red] 시트 ID 미설정.")
        raise typer.Exit(1)

    ws = open_sheet(sa_path, sheet_id, worksheet)
    ok, issues = verify_persona_schema(ws)
    if not ok:
        console.print("  [yellow]페르소나 스키마 불일치:[/yellow]")
        for i in issues:
            console.print(f"    {i}")
        raise typer.Exit(1)

    pending = fetch_persona_pending(ws)
    console.print(f"  처리 대상: {len(pending)}곡")
    if not pending:
        console.print("  [dim]Suno로 보낼 행 없음.[/dim]")
        return

    project_name = project or generate_project_name()

    for r in pending:
        sheet_row = r["sheet_row"]
        title = r.get("Title1", "")
        console.print(f"\n  [row {sheet_row}] {title}")

        mark_persona_processing(ws, sheet_row)
        try:
            req = row_to_persona_song_request(r)
            song = create_song(project_name, req)
            song.suno_title = req.suno_title
            song.suno_lyrics = req.suno_lyrics
            song.suno_tags = req.suno_tags
            song.suno_persona_id = req.suno_persona_id
            song.sheet_row = sheet_row
            song_dir = get_song_dir(project_name, song.id)

            # Suno
            song = generate_song_direct(config, song, song_dir)
            save_song_meta(project_name, song)
            gate3 = verify_gate3(song, song_dir)
            song.gates["gate3"] = gate3.to_dict()
            if not run_gate(gate3, "곡 생성"):
                mark_persona_failed(ws, sheet_row, "Gate 3 차단")
                continue

            # 이미지 (선택)
            if not skip_image:
                song = generate_images(config, song, song_dir)
                save_song_meta(project_name, song)
                gate4 = verify_gate4(song, song_dir)
                song.gates["gate4"] = gate4.to_dict()
                run_gate(gate4, "이미지 생성")

            # 시트 반영
            audio_url = song.suno_audio_url or ""
            mark_persona_done(ws, sheet_row, music_url=audio_url, song_id=song.id)
            save_song_meta(project_name, song)
            console.print(f"  [green]완료[/green]: {song.id}")

        except Exception as e:
            console.print(f"  [red][실패][/red] {e}")
            mark_persona_failed(ws, sheet_row, str(e))

    console.print(f"\n  프로젝트: {project_name}")
