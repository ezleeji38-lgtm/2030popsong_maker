"""CapCut 인박스/아웃박스 폴더 관리 + 곡별 자산 복사.

각 곡의 inbox 폴더 구조:
  ~/CapCut/inbox/<song_id>/
    audio.mp3            ← Suno 결과
    thumbnail.png        ← 썸네일 (Gemini 또는 시트의 외부 이미지)
    background.png       ← 배경 이미지 (있으면)
    title.txt            ← CapCut 텍스트 박스에 복붙용 1줄
    lyrics.txt           ← 가사 (자막용)
    youtube_meta.json    ← YouTube 업로드용 메타 (title, description, tags, timeline, localizations)
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from song_maker.models import Song

DEFAULT_INBOX = Path.home() / "CapCut" / "inbox"
DEFAULT_OUTBOX = Path.home() / "CapCut" / "outbox"


@dataclass
class CapCutPaths:
    inbox_root: Path
    outbox_root: Path

    def song_inbox(self, song_id: str) -> Path:
        return self.inbox_root / song_id

    def find_outbox_mp4(self, song_id: str) -> Path | None:
        """outbox에서 song_id에 매칭되는 mp4 파일 찾기.

        매칭 우선순위:
          1. <song_id>.mp4
          2. <song_id>_*.mp4
          3. *<song_id>*.mp4
        """
        if not self.outbox_root.exists():
            return None
        exact = self.outbox_root / f"{song_id}.mp4"
        if exact.exists():
            return exact
        for pattern in (f"{song_id}_*.mp4", f"*{song_id}*.mp4"):
            matches = sorted(self.outbox_root.glob(pattern))
            if matches:
                return matches[0]
        return None


def capcut_paths(config: dict | None = None) -> CapCutPaths:
    """config의 [capcut] 섹션에서 inbox/outbox 경로 읽기."""
    inbox = DEFAULT_INBOX
    outbox = DEFAULT_OUTBOX
    if config:
        cap = config.get("capcut", {}) or {}
        if cap.get("inbox_dir"):
            inbox = Path(cap["inbox_dir"]).expanduser()
        if cap.get("outbox_dir"):
            outbox = Path(cap["outbox_dir"]).expanduser()
    return CapCutPaths(inbox_root=inbox, outbox_root=outbox)


def handoff_song(
    song: Song,
    song_dir: Path,
    paths: CapCutPaths,
    *,
    external_thumbnail: Path | None = None,
) -> Path:
    """곡 파일들을 CapCut inbox로 복사.

    Args:
        song: songmaker의 Song 인스턴스 (audio_path, background_path, thumbnail_path 등)
        song_dir: 로컬 song 작업 디렉토리 (output/<project>/song_<id>/)
        paths: CapCutPaths
        external_thumbnail: 시트의 외부 썸네일 우선 사용 시 경로

    Returns:
        생성된 inbox 폴더 경로
    """
    inbox = paths.song_inbox(song.id)
    inbox.mkdir(parents=True, exist_ok=True)

    # 1. 오디오
    if song.audio_path:
        src = song_dir / song.audio_path
        if src.exists():
            shutil.copy2(src, inbox / "audio.mp3")

    # 2. 썸네일 — 외부 우선, 없으면 song.thumbnail_path
    thumb_target = inbox / "thumbnail.png"
    if external_thumbnail and external_thumbnail.exists():
        shutil.copy2(external_thumbnail, thumb_target)
    elif song.thumbnail_path:
        src = song_dir / song.thumbnail_path
        if src.exists():
            shutil.copy2(src, thumb_target)

    # 3. 배경
    if song.background_path:
        src = song_dir / song.background_path
        if src.exists():
            shutil.copy2(src, inbox / "background.png")

    # 4. 제목 텍스트 (CapCut 텍스트 박스 복붙용)
    title_text = song.suno_title or song.theme or song.id
    (inbox / "title.txt").write_text(title_text, encoding="utf-8")

    # 5. 가사
    if song.lyrics_path:
        src = song_dir / song.lyrics_path
        if src.exists():
            shutil.copy2(src, inbox / "lyrics.txt")
    elif song.suno_lyrics:
        (inbox / "lyrics.txt").write_text(song.suno_lyrics, encoding="utf-8")

    # 6. YouTube 메타 stub (나중에 Gemini 메타 생성기에서 채움)
    write_youtube_meta_stub(song, inbox / "youtube_meta.json")

    return inbox


def write_youtube_meta_stub(song: Song, target: Path) -> None:
    """YouTube 업로드용 메타데이터 stub 파일.

    나중에 Gemini로 후킹 제목/본문/타임라인/번역 채움.
    """
    title = song.suno_title or song.theme or song.id
    stub = {
        "song_id": song.id,
        "suno_title": title,
        "suno_tags": song.suno_tags or "",
        "suno_audio_url": song.suno_audio_url or "",
        "youtube_title": title,
        "youtube_description": "",
        "youtube_tags": [],
        "timeline": [],
        "localizations": {},
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    target.write_text(
        json.dumps(stub, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
