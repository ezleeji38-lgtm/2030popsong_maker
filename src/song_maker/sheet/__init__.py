"""Google Sheets 연동.

ChatGPT 챗봇이 가사/제목/태그를 시트에 기록하면 songmaker가 읽어서 처리.
Service Account 인증 사용.
"""

from song_maker.sheet.client import (
    HEADERS,
    append_pending_row,
    fetch_pending_rows,
    mark_done,
    mark_failed,
    mark_processing,
    open_sheet,
    row_external_thumbnail,
    row_to_song_request,
    verify_schema,
)
from song_maker.sheet.parse import ParsedRow, parse_chatbot_output

__all__ = [
    "HEADERS",
    "ParsedRow",
    "append_pending_row",
    "fetch_pending_rows",
    "mark_done",
    "mark_failed",
    "mark_processing",
    "open_sheet",
    "parse_chatbot_output",
    "row_external_thumbnail",
    "row_to_song_request",
    "verify_schema",
]
