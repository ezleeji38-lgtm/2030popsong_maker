"""Google Sheets 클라이언트. Service Account 인증 + 행 조회/갱신.

시트 스키마 (헤더 1행 고정):
| status | title | lyrics | tags | persona_id | image_prompt | thumbnail_path | song_id | audio_url | youtube_url | error | updated_at |

- 사용자 입력: title, lyrics, tags (필수) / persona_id, image_prompt, thumbnail_path (선택)
- songmaker 갱신: status, song_id, audio_url, youtube_url, error, updated_at
- status 값: pending / processing / done / failed
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

from song_maker.models import SongRequest

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

HEADERS: list[str] = [
    "status",         # A
    "title",          # B
    "lyrics",         # C
    "tags",           # D
    "persona_id",     # E (선택)
    "image_prompt",   # F (선택)
    "thumbnail_path", # G (선택, 시니어 채널 외부 썸네일 우선)
    "song_id",        # H (songmaker 채움)
    "audio_url",      # I (songmaker 채움)
    "youtube_url",    # J (songmaker 채움)
    "error",          # K (songmaker 채움)
    "updated_at",     # L (songmaker 채움)
]

# 컬럼 인덱스 (1-based, gspread 기준)
COL = {h: i + 1 for i, h in enumerate(HEADERS)}

VALID_STATUSES = {"pending", "processing", "done", "failed"}


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _load_credentials(service_account_path: str | Path) -> Credentials:
    """Service Account JSON 키 파일 로드."""
    path = Path(service_account_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(
            f"Service Account JSON 파일이 없습니다: {path}\n"
            f"GCP Console에서 발급 후 경로를 config.toml [sheets] service_account_path에 지정하세요."
        )
    return Credentials.from_service_account_file(str(path), scopes=SCOPES)


def open_sheet(service_account_path: str | Path, sheet_id: str, worksheet: str | None = None):
    """시트 열기. worksheet 지정 안 하면 첫 번째 시트."""
    creds = _load_credentials(service_account_path)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(sheet_id)
    if worksheet:
        return spreadsheet.worksheet(worksheet)
    return spreadsheet.sheet1


def verify_schema(ws) -> tuple[bool, list[str]]:
    """헤더 1행이 HEADERS와 일치하는지 검증."""
    actual = ws.row_values(1)
    issues: list[str] = []
    for i, h in enumerate(HEADERS):
        a = actual[i] if i < len(actual) else ""
        if a.strip() != h:
            issues.append(f"col {chr(ord('A') + i)}: '{a}' → '{h}'")
    return (len(issues) == 0, issues)


def fetch_pending_rows(ws) -> list[dict[str, Any]]:
    """status=pending 또는 빈 행만 추려서 반환.

    각 dict에 sheet_row(1-based 행번호) 포함.
    """
    all_rows = ws.get_all_records()  # 헤더 1행 기준 dict 리스트
    pending: list[dict[str, Any]] = []
    for idx, row in enumerate(all_rows, start=2):  # 데이터 시작은 2행
        status = (row.get("status") or "").strip().lower()
        if status not in ("", "pending"):
            continue
        title = (row.get("title") or "").strip()
        lyrics = (row.get("lyrics") or "").strip()
        tags = (row.get("tags") or "").strip()
        if not (title and lyrics and tags):
            # 미완성 행 스킵 (사용자가 작성 중일 수 있음)
            continue
        pending.append({**row, "sheet_row": idx})
    return pending


def row_to_song_request(row: dict[str, Any]) -> SongRequest:
    """시트 행 dict → SongRequest (direct 모드)."""
    return SongRequest(
        # 기존 필드는 placeholder (direct 모드에선 안 씀)
        genre="",
        mood="",
        theme=(row.get("title") or "")[:50],
        # direct 필드
        suno_title=(row.get("title") or "").strip(),
        suno_lyrics=(row.get("lyrics") or "").strip(),
        suno_tags=(row.get("tags") or "").strip(),
        suno_persona_id=(row.get("persona_id") or "").strip() or None,
        custom_image_prompt=(row.get("image_prompt") or "").strip() or None,
    )


def row_external_thumbnail(row: dict[str, Any]) -> str:
    """시트 행에서 thumbnail_path 추출 (시니어 채널 외부 썸네일)."""
    return (row.get("thumbnail_path") or "").strip()


def _batch_update_cells(ws, sheet_row: int, updates: dict[str, str]) -> None:
    """여러 컬럼을 batch_update로 한 번에 갱신 (API 호출 1회).

    updates: {"status": "done", "song_id": "abc", ...}
    """
    from gspread.utils import rowcol_to_a1

    payload = []
    for header, value in updates.items():
        if header not in COL:
            continue
        cell = rowcol_to_a1(sheet_row, COL[header])
        payload.append({"range": cell, "values": [[value]]})
    if payload:
        ws.batch_update(payload)


def mark_processing(ws, sheet_row: int) -> None:
    """status=processing, updated_at 갱신 (batch update — API 1회)."""
    _batch_update_cells(ws, sheet_row, {
        "status": "processing",
        "updated_at": _now_iso(),
    })


def mark_done(ws, sheet_row: int, *, song_id: str, audio_url: str = "", youtube_url: str = "") -> None:
    """status=done + 메타 모두 한 번에 기록."""
    updates = {
        "status": "done",
        "song_id": song_id,
        "error": "",
        "updated_at": _now_iso(),
    }
    if audio_url:
        updates["audio_url"] = audio_url
    if youtube_url:
        updates["youtube_url"] = youtube_url
    _batch_update_cells(ws, sheet_row, updates)


def append_pending_row(
    ws,
    *,
    title: str,
    lyrics: str,
    tags: str,
    persona_id: str = "",
    image_prompt: str = "",
    thumbnail_path: str = "",
) -> int:
    """시트 끝에 status=pending 행 추가. 새 행 번호 반환.

    HEADERS와 같은 순서로 값을 쭉 채움.
    """
    row_values = [
        "pending",          # status
        title,              # title
        lyrics,             # lyrics
        tags,               # tags
        persona_id,         # persona_id
        image_prompt,       # image_prompt
        thumbnail_path,     # thumbnail_path
        "",                 # song_id
        "",                 # audio_url
        "",                 # youtube_url
        "",                 # error
        _now_iso(),         # updated_at
    ]
    ws.append_row(row_values, value_input_option="RAW")
    # 새 행 번호 추정: 다음 비어있는 행
    return len(ws.col_values(1))


def mark_failed(ws, sheet_row: int, error: str) -> None:
    """status=failed + error 메시지 한 번에 기록."""
    _batch_update_cells(ws, sheet_row, {
        "status": "failed",
        "error": error[:500],
        "updated_at": _now_iso(),
    })
