"""페르소나 메이크 자동화 시트 어댑터.

사용자의 기존 시트 구조 (12컬럼) 그대로 사용:
| A:Index | B:Status | C:Title1 (영문) | D:Title2 (한글) | E:Subject |
| F:Original Song | G:Original Lyric | H:Tag | I:Neg_tag | J:Song Lyric |
| K:Music URL | L:Persona ID |

흐름:
1. 사용자 (또는 챗봇)이 C/D/E + F/G + H/I + L 채움
2. `songmaker transform-batch` 또는 수동으로 J 채움 (G + C + E → Claude/Gemini 5규칙 변환)
3. `songmaker batch-persona` — J 채워진 행을 Suno로 보냄
4. 완료 시 K(Music URL) 갱신 + B(Status) = DONE
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from gspread.utils import rowcol_to_a1

from song_maker.models import SongRequest

PERSONA_HEADERS: list[str] = [
    "Index",          # A — 자동 또는 사용자 입력 (작업 안 함)
    "Status",         # B — empty/pending/DO IT → processing → DONE/FAILED
    "Title1",         # C — 영어 제목 (Suno Title 직결)
    "Title2",         # D — 한국어 제목 (참고용)
    "Subject",        # E — 가사 내용·감정 한국어 설명
    "Original Song",  # F — 원곡 제목 (참고)
    "Original Lyric", # G — 원곡 가사 (transform 입력)
    "Tag",            # H — Suno positive tag
    "Neg_tag",        # I — Suno negative tag (참고용, suno-api는 기본 미지원)
    "Song Lyric",     # J — 변환된 새 가사 (transform 출력 = Suno Lyrics 입력)
    "Music URL",      # K — Suno 결과 audio_url
    "Persona ID",     # L — Suno persona UUID (보컬 일관성)
]

PERSONA_COL = {h: i + 1 for i, h in enumerate(PERSONA_HEADERS)}

# 트리거로 인정되는 Status 값 (소문자 비교)
TRIGGER_STATUSES = {"", "do it", "doit", "pending", "ready"}


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def verify_persona_schema(ws) -> tuple[bool, list[str]]:
    """헤더 1행이 PERSONA_HEADERS와 일치하는지 검증."""
    actual = ws.row_values(1)
    issues: list[str] = []
    for i, h in enumerate(PERSONA_HEADERS):
        a = actual[i] if i < len(actual) else ""
        if a.strip() != h:
            issues.append(f"col {chr(ord('A') + i)}: '{a}' → '{h}'")
    return (len(issues) == 0, issues)


def fetch_persona_pending(ws) -> list[dict[str, Any]]:
    """Status가 트리거 값이고 Song Lyric(J)이 채워진 행만 반환.

    각 dict에 sheet_row(1-based 행번호) 포함.
    """
    all_rows = ws.get_all_records()
    pending: list[dict[str, Any]] = []
    for idx, row in enumerate(all_rows, start=2):
        status = (row.get("Status") or "").strip().lower()
        if status not in TRIGGER_STATUSES:
            continue
        song_lyric = (row.get("Song Lyric") or "").strip()
        title = (row.get("Title1") or "").strip()
        tag = (row.get("Tag") or "").strip()
        # Suno로 보내려면 가사 + 제목 + 태그 모두 필요
        if not (song_lyric and title and tag):
            continue
        pending.append({**row, "sheet_row": idx})
    return pending


def fetch_persona_needs_transform(ws) -> list[dict[str, Any]]:
    """가사 변환이 필요한 행만 반환 — G(원가사) 있고 J(새가사) 비어있는 행."""
    all_rows = ws.get_all_records()
    needs: list[dict[str, Any]] = []
    for idx, row in enumerate(all_rows, start=2):
        status = (row.get("Status") or "").strip().lower()
        if status in ("done", "failed", "processing"):
            continue
        original = (row.get("Original Lyric") or "").strip()
        new_title = (row.get("Title1") or "").strip()
        subject = (row.get("Subject") or "").strip()
        song_lyric = (row.get("Song Lyric") or "").strip()
        # 원가사·제목·내용 있고 새가사는 비어 있어야 변환 대상
        if original and new_title and subject and not song_lyric:
            needs.append({**row, "sheet_row": idx})
    return needs


def row_to_persona_song_request(row: dict[str, Any]) -> SongRequest:
    """페르소나 행 dict → SongRequest (direct 모드)."""
    return SongRequest(
        genre="",
        mood="",
        theme=(row.get("Subject") or "")[:50],
        suno_title=(row.get("Title1") or "").strip(),
        suno_lyrics=(row.get("Song Lyric") or "").strip(),
        suno_tags=(row.get("Tag") or "").strip(),
        suno_persona_id=(row.get("Persona ID") or "").strip() or None,
    )


def _batch_update_persona(ws, sheet_row: int, updates: dict[str, str]) -> None:
    """페르소나 컬럼 일괄 갱신."""
    payload = []
    for header, value in updates.items():
        if header not in PERSONA_COL:
            continue
        cell = rowcol_to_a1(sheet_row, PERSONA_COL[header])
        payload.append({"range": cell, "values": [[value]]})
    if payload:
        ws.batch_update(payload)


def mark_persona_processing(ws, sheet_row: int) -> None:
    """Status=processing."""
    _batch_update_persona(ws, sheet_row, {"Status": "processing"})


def mark_persona_done(
    ws,
    sheet_row: int,
    *,
    music_url: str = "",
    song_id: str = "",
) -> None:
    """Status=DONE + Music URL 기록."""
    updates = {"Status": "DONE"}
    if music_url:
        updates["Music URL"] = music_url
    _batch_update_persona(ws, sheet_row, updates)


def mark_persona_failed(ws, sheet_row: int, error: str) -> None:
    """Status=FAILED + 에러 메시지를 Music URL 컬럼에 임시 기록."""
    _batch_update_persona(ws, sheet_row, {
        "Status": "FAILED",
        "Music URL": f"[error] {error[:200]}",
    })


def write_transformed_lyric(ws, sheet_row: int, new_lyric: str) -> None:
    """J열(Song Lyric)에 변환된 가사 기록."""
    _batch_update_persona(ws, sheet_row, {"Song Lyric": new_lyric})


def append_persona_seed(
    ws,
    *,
    title_en: str,
    title_kr: str,
    subject_kr: str,
    original_song: str = "",
    original_lyric: str = "",
    tag: str = "",
    neg_tag: str = "",
    persona_id: str = "",
) -> int:
    """시트 끝에 시드 한 행 추가. Status는 비워둠(트리거 대기)."""
    row_values = [
        "",                # Index (시트에 자동 채우는 함수 있을 수 있음)
        "",                # Status (비워두면 트리거 대기 — 사용자가 DO IT으로 변경)
        title_en,          # Title1
        title_kr,          # Title2
        subject_kr,        # Subject
        original_song,     # Original Song
        original_lyric,    # Original Lyric
        tag,               # Tag
        neg_tag,           # Neg_tag
        "",                # Song Lyric (transform 대기)
        "",                # Music URL (Suno 대기)
        persona_id,        # Persona ID
    ]
    ws.append_row(row_values, value_input_option="RAW")
    return len(ws.col_values(1))
