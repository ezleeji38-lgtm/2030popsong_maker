"""공유 데이터 모델. Pydantic BaseModel 기반."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TrendItem(BaseModel):
    """YouTube 트렌드 음악 항목."""

    rank: int
    title: str
    artist: str
    view_count: int
    tags: list[str] = Field(default_factory=list)
    video_id: str
    published_at: str


class TrendReport(BaseModel):
    """트렌드 조사 결과."""

    region: str
    items: list[TrendItem]
    top_genres: list[str] = Field(default_factory=list)
    top_keywords: list[str] = Field(default_factory=list)
    fetched_at: datetime = Field(default_factory=datetime.now)


class SongRequest(BaseModel):
    """사용자 곡 생성 요청.

    - 대화형 모드: genre/mood/theme/lyrics_keywords로 Suno에 위임
    - direct 모드 (시트 배치): suno_title/suno_lyrics/suno_tags 직접 주입
    """

    genre: str
    mood: str
    theme: str
    lyrics_keywords: list[str] = Field(default_factory=list)
    reference_song: str | None = None
    count: int = 1

    # direct 모드: 시트에서 가사/제목/태그를 직접 받을 때 사용
    suno_title: str | None = None
    suno_lyrics: str | None = None
    suno_tags: str | None = None
    suno_persona_id: str | None = None
    custom_image_prompt: str | None = None


class Song(BaseModel):
    """곡 메타데이터. output/{project}/{song_id}/meta.json에 저장."""

    id: str
    genre: str
    mood: str
    theme: str
    lyrics_keywords: list[str] = Field(default_factory=list)
    reference_song: str | None = None
    audio_path: str | None = None
    lyrics_path: str | None = None
    background_path: str | None = None
    thumbnail_path: str | None = None
    video_path: str | None = None
    youtube_url: str | None = None
    status: str = "created"
    image_model: str | None = None
    image_prompt: str | None = None
    render_options: dict[str, Any] = Field(default_factory=dict)
    gates: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    uploaded_at: datetime | None = None

    # direct 모드 (시트 배치)
    suno_title: str | None = None
    suno_lyrics: str | None = None
    suno_tags: str | None = None
    suno_persona_id: str | None = None
    suno_audio_url: str | None = None
    suno_song_id: str | None = None
    custom_image_prompt: str | None = None
    sheet_row: int | None = None  # 시트 행 번호 (업데이트 시 사용)


class Project(BaseModel):
    """프로젝트 메타데이터. output/{project}/meta.json에 저장."""

    name: str
    songs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
