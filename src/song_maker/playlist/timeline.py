"""플레이리스트 타임라인 빌더.

원본 JS 앱(제이린쌤 플리 타임라인 자동 생성기)의 결정론적 로직을 Python으로 포팅.

흐름:
  mp3 폴더 → 파일명 숫자 정렬 → 각 파일 duration(ffprobe) → 누적 시간 → MM:SS - 제목
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from song_maker.renderer.ffmpeg import get_audio_duration

HEADER = "🎵 Time Track"

# "01 - title.mp3", "01. title.mp3", "1_title.mp3" 등의 prefix 제거
TITLE_PREFIX_RE = re.compile(r"^\d+[\s.\-_]+")


@dataclass
class PlaylistEntry:
    file: Path
    title: str
    start_seconds: float
    duration: float

    @property
    def timestamp(self) -> str:
        return format_timestamp(self.start_seconds)

    def line(self) -> str:
        return f"{self.timestamp} - {self.title}"


def format_timestamp(seconds: float) -> str:
    """초 → MM:SS 또는 H:MM:SS (1시간 이상)."""
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def extract_title(filename: str) -> str:
    """파일명에서 prefix(번호)와 확장자 제거하여 제목 추출."""
    stem = Path(filename).stem
    no_prefix = TITLE_PREFIX_RE.sub("", stem).strip()
    return no_prefix or stem


def _natural_sort_key(p: Path) -> tuple:
    """파일명 안의 숫자를 자연 정렬 (1, 2, 10 순서)."""
    parts = re.split(r"(\d+)", p.name)
    return tuple(int(x) if x.isdigit() else x.lower() for x in parts)


def collect_mp3s(folder: Path) -> list[Path]:
    """폴더에서 mp3 파일들을 자연 정렬로 수집 (재귀 X)."""
    if not folder.exists() or not folder.is_dir():
        return []
    files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".mp3"]
    files.sort(key=_natural_sort_key)
    return files


def build_timeline(
    mp3_paths: list[Path],
    *,
    header: str = HEADER,
) -> tuple[str, list[PlaylistEntry]]:
    """mp3 경로 리스트 → (타임라인 텍스트, 엔트리 리스트).

    Args:
        mp3_paths: 정렬된 mp3 파일 경로
        header: 첫 줄에 들어갈 헤더

    Returns:
        ("🎵 Time Track\n00:00 - Title 1\n...", [PlaylistEntry, ...])
    """
    entries: list[PlaylistEntry] = []
    current = 0.0
    for mp3 in mp3_paths:
        duration = get_audio_duration(mp3)
        if duration <= 0:
            # ffprobe 실패 시 그대로 진행 (start만 기록)
            duration = 0.0
        title = extract_title(mp3.name)
        entries.append(PlaylistEntry(
            file=mp3,
            title=title,
            start_seconds=current,
            duration=duration,
        ))
        current += duration

    lines = [header]
    lines.extend(e.line() for e in entries)
    return "\n".join(lines), entries
