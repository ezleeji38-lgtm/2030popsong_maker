"""CapCut 핸드오프 — songmaker가 만든 mp3/이미지를 CapCut에서 import 가능한 폴더에 정리.

흐름:
  songmaker → ~/CapCut/inbox/<song_id>/ 에 파일 저장
            → 사용자가 CapCut 열어서 import → 편집 → mp4 export
            → ~/CapCut/outbox/<song_id>.mp4
            → songmaker upload-capcut <mp4>
"""

from song_maker.capcut.handoff import (
    DEFAULT_INBOX,
    DEFAULT_OUTBOX,
    CapCutPaths,
    capcut_paths,
    handoff_song,
    write_youtube_meta_stub,
)

__all__ = [
    "DEFAULT_INBOX",
    "DEFAULT_OUTBOX",
    "CapCutPaths",
    "capcut_paths",
    "handoff_song",
    "write_youtube_meta_stub",
]
