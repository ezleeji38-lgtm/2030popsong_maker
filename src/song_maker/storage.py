"""output/ 저장 관리. Project/Song meta.json 읽기/쓰기.

OUTPUT_DIR 결정 우선순위:
  1) 환경변수 SONGMAKER_OUTPUT_DIR
  2) config.toml [output] dir
  3) 현재 작업 디렉토리의 ./output (기본)
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from song_maker.models import Project, Song, SongRequest


def _resolve_output_dir() -> Path:
    """출력 디렉토리 결정 (호출 시점에 동적 계산)."""
    # 1) 환경변수
    env = os.environ.get("SONGMAKER_OUTPUT_DIR", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    # 2) config 파일
    try:
        from song_maker import config as _cfg
        c = _cfg.load_config()
        configured = (c.get("output", {}) or {}).get("dir", "").strip()
        if configured:
            return Path(configured).expanduser().resolve()
    except Exception:
        pass
    # 3) 기본: cwd/output
    return Path.cwd() / "output"


# 호환성을 위해 모듈 레벨 변수도 유지 (import 시점 고정)
OUTPUT_DIR = _resolve_output_dir()


def ensure_output_dir() -> Path:
    """출력 디렉토리 보장. 호출 시점에 다시 계산하여 cron 등에서 안전하게."""
    p = _resolve_output_dir()
    p.mkdir(parents=True, exist_ok=True)
    return p


def generate_song_id() -> str:
    return uuid.uuid4().hex[:8]


def generate_project_name() -> str:
    return f"project_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def get_project_dir(project_name: str) -> Path:
    return ensure_output_dir() / project_name


def get_song_dir(project_name: str, song_id: str) -> Path:
    return get_project_dir(project_name) / f"song_{song_id}"


def create_song(project_name: str, request: SongRequest) -> Song:
    """SongRequest로부터 Song을 생성하고 디렉토리 + meta.json을 만든다."""
    song_id = generate_song_id()
    song_dir = get_song_dir(project_name, song_id)
    song_dir.mkdir(parents=True, exist_ok=True)

    song = Song(
        id=song_id,
        genre=request.genre,
        mood=request.mood,
        theme=request.theme,
        lyrics_keywords=request.lyrics_keywords,
        reference_song=request.reference_song,
    )
    save_song_meta(project_name, song)
    return song


def save_song_meta(project_name: str, song: Song) -> None:
    """Song meta.json 저장."""
    song_dir = get_song_dir(project_name, song.id)
    song_dir.mkdir(parents=True, exist_ok=True)
    meta_path = song_dir / "meta.json"

    # model_dump_json은 datetime을 ISO 문자열로 직렬화함
    data = json.loads(song.model_dump_json())

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_song_meta(project_name: str, song_id: str) -> Song:
    """Song meta.json 로드."""
    meta_path = get_song_dir(project_name, song_id) / "meta.json"
    with open(meta_path, encoding="utf-8") as f:
        data = json.load(f)
    return Song(**data)


def save_project_meta(project_name: str, song_ids: list[str]) -> None:
    """Project meta.json 저장."""
    project_dir = get_project_dir(project_name)
    project_dir.mkdir(parents=True, exist_ok=True)
    meta_path = project_dir / "meta.json"

    project = Project(name=project_name, songs=song_ids)
    data = json.loads(project.model_dump_json())

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def list_all_songs() -> list[tuple[str, Song]]:
    """모든 프로젝트의 모든 곡을 반환. [(project_name, Song), ...]

    중간에 디렉토리/파일이 사라져도 가능한 항목은 포함하여 반환.
    """
    results: list[tuple[str, Song]] = []
    output_dir = _resolve_output_dir()
    if not output_dir.exists():
        return results

    try:
        project_dirs = sorted(output_dir.iterdir())
    except FileNotFoundError:
        return results

    for project_dir in project_dirs:
        if not project_dir.is_dir():
            continue
        try:
            song_dirs = sorted(project_dir.iterdir())
        except FileNotFoundError:
            continue
        for song_dir in song_dirs:
            if not song_dir.is_dir() or not song_dir.name.startswith("song_"):
                continue
            meta_path = song_dir / "meta.json"
            try:
                with open(meta_path, encoding="utf-8") as f:
                    data = json.load(f)
                results.append((project_dir.name, Song(**data)))
            except (FileNotFoundError, json.JSONDecodeError):
                continue
    return results
