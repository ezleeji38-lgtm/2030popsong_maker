"""Google Drive 일별 가사 정리.

흐름:
  songmaker batch 처리 시 → SongMaker/<YYYY-MM-DD>/<title>.txt 자동 생성

전제: Service Account가 부모 폴더에 편집자로 공유돼있어야 함.
"""

from song_maker.drive.client import (
    archive_lyrics,
    ensure_date_folder,
    open_drive,
)

__all__ = [
    "archive_lyrics",
    "ensure_date_folder",
    "open_drive",
]
