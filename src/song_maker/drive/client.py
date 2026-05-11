"""Google Drive 클라이언트 — Service Account 인증, 폴더/파일 생성.

가사를 SongMaker/<YYYY-MM-DD>/<song_id>_<title>.txt 형태로 자동 정리.
"""

from __future__ import annotations

import io
import re
from datetime import datetime
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

SCOPES = [
    "https://www.googleapis.com/auth/drive",
]

FOLDER_MIME = "application/vnd.google-apps.folder"
TEXT_MIME = "text/plain"


def _load_credentials(service_account_path: str | Path) -> Credentials:
    path = Path(service_account_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Service Account JSON 없음: {path}")
    return Credentials.from_service_account_file(str(path), scopes=SCOPES)


def open_drive(service_account_path: str | Path):
    """Drive API 서비스 객체."""
    creds = _load_credentials(service_account_path)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _find_folder_by_name(drive, name: str, parent_id: str | None = None) -> str | None:
    """이름으로 폴더 검색. 첫 번째 매칭 ID 반환."""
    safe_name = name.replace("'", "\\'")
    q_parts = [
        f"name = '{safe_name}'",
        f"mimeType = '{FOLDER_MIME}'",
        "trashed = false",
    ]
    if parent_id:
        q_parts.append(f"'{parent_id}' in parents")
    q = " and ".join(q_parts)
    resp = drive.files().list(
        q=q,
        fields="files(id, name)",
        pageSize=10,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    files = resp.get("files", [])
    return files[0]["id"] if files else None


def _create_folder(drive, name: str, parent_id: str | None = None) -> str:
    body = {"name": name, "mimeType": FOLDER_MIME}
    if parent_id:
        body["parents"] = [parent_id]
    file = drive.files().create(
        body=body, fields="id", supportsAllDrives=True
    ).execute()
    return file["id"]


def ensure_date_folder(
    drive,
    parent_folder_id: str,
    date_str: str | None = None,
) -> str:
    """SongMaker 부모 폴더 안에 YYYY-MM-DD 폴더가 없으면 생성. ID 반환."""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    existing = _find_folder_by_name(drive, date_str, parent_id=parent_folder_id)
    if existing:
        return existing
    return _create_folder(drive, date_str, parent_id=parent_folder_id)


SAFE_FILENAME_RE = re.compile(r"[^\w가-힣\-_. ]+")


def _safe_filename(name: str, max_len: int = 80) -> str:
    cleaned = SAFE_FILENAME_RE.sub("_", name).strip("_ .")
    if not cleaned:
        cleaned = "untitled"
    return cleaned[:max_len]


def archive_lyrics(
    drive,
    parent_folder_id: str,
    song_id: str,
    title: str,
    lyrics: str,
    date_str: str | None = None,
) -> str:
    """가사를 일별 폴더에 .txt로 업로드. file_id 반환.

    파일명: <song_id>_<title>.txt
    """
    if not lyrics.strip():
        raise ValueError("lyrics 비어있음 — 업로드 안 함")

    date_folder_id = ensure_date_folder(drive, parent_folder_id, date_str)
    fname = f"{song_id}_{_safe_filename(title)}.txt"

    media = MediaIoBaseUpload(
        io.BytesIO(lyrics.encode("utf-8")),
        mimetype=TEXT_MIME,
        resumable=False,
    )
    body = {"name": fname, "parents": [date_folder_id]}
    file = drive.files().create(
        body=body,
        media_body=media,
        fields="id",
        supportsAllDrives=True,
    ).execute()
    return file["id"]
