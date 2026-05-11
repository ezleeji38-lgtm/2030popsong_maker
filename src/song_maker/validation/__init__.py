"""사전 검증 모듈.

- duplicate: 새 가사가 기존 가사와 너무 유사하면 Suno 호출 차단
- lint: 시트 행의 title/lyrics/tags 형식 검증 (Suno 호출 전 사전 검사)
"""

from song_maker.validation.duplicate import (
    DUPLICATE_THRESHOLD,
    DuplicateMatch,
    check_duplicate,
    check_duplicate_within_batch,
    load_existing_lyrics,
    normalize_lyrics,
)
from song_maker.validation.lint import (
    LintIssue,
    lint_row,
    lint_song_request,
)

__all__ = [
    "DUPLICATE_THRESHOLD",
    "DuplicateMatch",
    "LintIssue",
    "check_duplicate",
    "check_duplicate_within_batch",
    "lint_row",
    "lint_song_request",
    "load_existing_lyrics",
    "normalize_lyrics",
]
