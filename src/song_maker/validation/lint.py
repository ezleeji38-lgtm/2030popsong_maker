"""시트 행 / SongRequest의 형식 검증.

Suno 호출 전에 이상한 입력 사전 차단:
- title: 길이/문자
- lyrics: 섹션 마커, 최소 길이
- tags: BPM 숫자 형식, 알려진 style/vocal 키워드
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from song_maker.models import SongRequest

# 알려진 키워드 (참고용 — 미일치해도 차단 안 함, warning만)
KNOWN_VOCALS = {"male", "female", "duet", "instrumental"}
KNOWN_STYLES = {
    "pop", "minimal pop", "modern pop", "easy pop", "soft pop",
    "r&b pop", "rnb pop", "hip hop", "k-pop", "kpop",
    "billboard pop", "indie pop", "dream pop",
    "ballad", "soft rock", "country", "folk",
    "lofi", "lo-fi", "ambient", "jazz", "acoustic",
}

BPM_RE = re.compile(r"\b(\d{2,3})\s*bpm\b", re.IGNORECASE)
SECTION_RE = re.compile(r"\[(verse|chorus|hook|bridge|intro|outro|pre[- ]?chorus|sub[- ]?chorus|rap|instrumental|final[- ]?chorus)[^\]]*\]", re.IGNORECASE)


@dataclass
class LintIssue:
    field: str
    severity: str  # "error" / "warning"
    message: str

    def __str__(self) -> str:
        tag = "ERROR" if self.severity == "error" else "WARN "
        return f"[{tag}] {self.field}: {self.message}"


# Suno API의 prompt(lyrics) 한도 ~5000자, title 한도 ~80자 (보수적 추정)
SUNO_LYRICS_HARD_LIMIT = 5000
SUNO_TITLE_HARD_LIMIT = 80
LYRICS_MIN_AFTER_MARKERS = 30  # 섹션 마커 제거 후 최소 글자 수


def _check_title(title: str) -> list[LintIssue]:
    issues: list[LintIssue] = []
    if not title or not title.strip():
        issues.append(LintIssue("title", "error", "title이 비어있습니다."))
        return issues
    t = title.strip()
    if len(t) > 100:
        issues.append(LintIssue("title", "warning", f"title 길이 {len(t)}자 (YouTube 제목 100자 초과)"))
    if len(t) > SUNO_TITLE_HARD_LIMIT:
        issues.append(LintIssue(
            "title", "warning",
            f"title이 Suno title 한도({SUNO_TITLE_HARD_LIMIT}자) 초과 — Suno에서 잘릴 수 있음"
        ))
    if len(t) < 3:
        issues.append(LintIssue("title", "warning", f"title이 너무 짧습니다 ({len(t)}자)"))
    return issues


def _check_lyrics(lyrics: str) -> list[LintIssue]:
    """lyrics 검증.

    - 빈 lyrics → ERROR
    - 마커 제거 후 빈 본문 → ERROR (마커만 있고 가사 없음)
    - Suno 한도 초과 → ERROR (호출 차단)
    - 섹션 마커 없음 → WARN
    - 너무 짧음 → WARN
    """
    issues: list[LintIssue] = []
    if not lyrics or not lyrics.strip():
        issues.append(LintIssue("lyrics", "error", "lyrics가 비어있습니다."))
        return issues
    text = lyrics.strip()

    # 마커 제거 후 본문이 거의 없으면 차단
    from song_maker.validation.duplicate import normalize_lyrics
    body_only = normalize_lyrics(text)
    if len(body_only) < LYRICS_MIN_AFTER_MARKERS:
        issues.append(LintIssue(
            "lyrics", "error",
            f"섹션 마커 제외하면 본문이 {len(body_only)}자 — 실제 가사가 부족합니다."
        ))
        # 너무 빈 가사면 다른 검사 건너뜀
        return issues

    # Suno 한도 초과는 ERROR
    if len(text) > SUNO_LYRICS_HARD_LIMIT:
        issues.append(LintIssue(
            "lyrics", "error",
            f"lyrics가 {len(text)}자 — Suno 한도(~{SUNO_LYRICS_HARD_LIMIT}자) 초과로 호출 거부 가능"
        ))

    # 너무 짧음 (WARN)
    if len(text) < 50:
        issues.append(LintIssue("lyrics", "warning", f"lyrics가 매우 짧습니다 ({len(text)}자) — Suno 결과 품질 저하 가능"))

    # 섹션 마커 없음 (WARN)
    if not SECTION_RE.search(text):
        issues.append(LintIssue(
            "lyrics", "warning",
            "섹션 마커([Verse]/[Chorus] 등) 없음 — Suno가 구조 인식 못 할 수 있음"
        ))

    return issues


def _check_tags(tags: str) -> list[LintIssue]:
    issues: list[LintIssue] = []
    if not tags or not tags.strip():
        issues.append(LintIssue("tags", "error", "tags가 비어있습니다."))
        return issues
    t = tags.strip()
    if len(t) > 200:
        issues.append(LintIssue("tags", "warning", f"tags가 깁니다 ({len(t)}자) — 200자 이내 권장"))

    # BPM 검증 (선택)
    bpm_match = BPM_RE.search(t)
    if bpm_match:
        bpm = int(bpm_match.group(1))
        if not (40 <= bpm <= 200):
            issues.append(LintIssue("tags", "warning", f"BPM {bpm} — 일반적 범위(60~180) 벗어남"))

    # 보컬/스타일 키워드 인지 (소프트 체크)
    lower = t.lower()
    has_vocal = any(v in lower for v in KNOWN_VOCALS)
    has_style = any(s in lower for s in KNOWN_STYLES)
    if not has_vocal:
        issues.append(LintIssue("tags", "warning", "vocal 키워드(male/female/duet) 인식 안 됨 — Suno 결정에 맡김"))
    if not has_style:
        issues.append(LintIssue("tags", "warning", "알려진 style 키워드 인식 안 됨 (커스텀 스타일이면 무시)"))

    return issues


def lint_song_request(req: SongRequest) -> list[LintIssue]:
    """SongRequest의 direct 모드 필드를 검증."""
    issues: list[LintIssue] = []
    issues.extend(_check_title(req.suno_title or ""))
    issues.extend(_check_lyrics(req.suno_lyrics or ""))
    issues.extend(_check_tags(req.suno_tags or ""))
    return issues


def lint_row(row: dict) -> list[LintIssue]:
    """시트 행 dict를 검증."""
    issues: list[LintIssue] = []
    issues.extend(_check_title((row.get("title") or "").strip()))
    issues.extend(_check_lyrics((row.get("lyrics") or "").strip()))
    issues.extend(_check_tags((row.get("tags") or "").strip()))
    return issues
