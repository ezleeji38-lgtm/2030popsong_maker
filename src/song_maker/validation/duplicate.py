"""중복 가사 감지.

원리: difflib.SequenceMatcher의 ratio()로 유사도(0~1) 계산.
- 0.75 이상: 차단 (의심스러울 정도로 유사)
- 0.50~0.75: 경고만
- 0.50 미만: 통과
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable

DUPLICATE_THRESHOLD = 0.75


@dataclass
class DuplicateMatch:
    """매칭 결과 한 건."""

    similarity: float
    matched_id: str  # 기존 곡 식별자 (song_id 또는 sheet_row)
    matched_source: str  # "sheet" / "local" / "drive"
    matched_title: str = ""
    snippet: str = ""  # 매칭된 가사 일부 (디버깅용)

    def is_blocking(self, threshold: float = DUPLICATE_THRESHOLD) -> bool:
        return self.similarity >= threshold


SECTION_MARKER_RE = re.compile(r"\[[^\]]+\]")
WHITESPACE_RE = re.compile(r"\s+")


def normalize_lyrics(text: str) -> str:
    """가사 정규화 — 섹션 마커 제거, 소문자, 공백 정리.

    유사도 비교 시 [Verse 1] / [Chorus] 같은 마커가 매칭 점수를 부풀리는 걸 방지.
    """
    if not text:
        return ""
    no_markers = SECTION_MARKER_RE.sub(" ", text)
    lower = no_markers.lower()
    cleaned = WHITESPACE_RE.sub(" ", lower).strip()
    return cleaned


def _similarity(a: str, b: str) -> float:
    """두 가사의 유사도 (0~1)."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def load_existing_lyrics(
    sheet_lyrics: Iterable[tuple[str, str, str]] | None = None,
    output_dir: Path | None = None,
) -> list[tuple[str, str, str, str]]:
    """기존 가사 로드.

    Returns:
        [(source, id, title, normalized_lyrics), ...]
        source: "sheet" / "local"
    """
    items: list[tuple[str, str, str, str]] = []

    # 시트에서 (id, title, lyrics) tuples 받음
    if sheet_lyrics:
        for sid, title, lyrics in sheet_lyrics:
            norm = normalize_lyrics(lyrics)
            if norm:
                items.append(("sheet", sid, title, norm))

    # 로컬 output 디렉토리 스캔
    if output_dir and output_dir.exists():
        for project_dir in output_dir.iterdir():
            if not project_dir.is_dir():
                continue
            for song_dir in project_dir.iterdir():
                if not song_dir.is_dir() or not song_dir.name.startswith("song_"):
                    continue
                lyrics_file = song_dir / "lyrics.txt"
                if not lyrics_file.exists():
                    continue
                try:
                    text = lyrics_file.read_text(encoding="utf-8")
                except OSError:
                    continue
                # meta.json에서 title/id 추출
                meta_file = song_dir / "meta.json"
                song_id = song_dir.name.replace("song_", "")
                title = ""
                if meta_file.exists():
                    try:
                        meta = json.loads(meta_file.read_text(encoding="utf-8"))
                        song_id = meta.get("id", song_id)
                        title = meta.get("suno_title") or meta.get("theme") or ""
                    except (OSError, json.JSONDecodeError):
                        pass
                norm = normalize_lyrics(text)
                if norm:
                    items.append(("local", song_id, title, norm))

    return items


def check_duplicate(
    new_lyrics: str,
    existing: list[tuple[str, str, str, str]],
    threshold: float = DUPLICATE_THRESHOLD,
) -> DuplicateMatch | None:
    """새 가사가 기존 가사와 임계값 이상 유사하면 매칭 반환.

    None이면 통과.
    """
    new_norm = normalize_lyrics(new_lyrics)
    if not new_norm:
        return None

    best: DuplicateMatch | None = None
    for source, sid, title, existing_norm in existing:
        sim = _similarity(new_norm, existing_norm)
        if sim < 0.30:
            continue  # 빠른 필터링
        if best is None or sim > best.similarity:
            best = DuplicateMatch(
                similarity=sim,
                matched_id=sid,
                matched_source=source,
                matched_title=title,
                snippet=existing_norm[:120],
            )

    if best and best.similarity >= threshold:
        return best
    return None


def check_duplicate_within_batch(
    candidates: list[tuple[str, str]],
    threshold: float = DUPLICATE_THRESHOLD,
) -> list[tuple[int, int, float]]:
    """배치 내부 중복 검사 (시트의 pending 행들끼리 비교).

    Args:
        candidates: [(id, lyrics), ...]

    Returns:
        [(i, j, similarity), ...] — 임계값 초과 쌍들
    """
    matches: list[tuple[int, int, float]] = []
    norms = [(cid, normalize_lyrics(lyr)) for cid, lyr in candidates]
    for i in range(len(norms)):
        for j in range(i + 1, len(norms)):
            sim = _similarity(norms[i][1], norms[j][1])
            if sim >= threshold:
                matches.append((i, j, sim))
    return matches
