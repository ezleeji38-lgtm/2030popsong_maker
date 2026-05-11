"""Gemini 기반 YouTube 메타데이터 다국어 번역.

원본: 제이린쌤 유튜브 추출기 & 번역기 (AI Studio 31c9d043).
"""

from song_maker.translator.translate import (
    DEFAULT_LANGUAGES,
    LOCALE_MAP,
    TranslationResult,
    korean_to_locale,
    to_youtube_localizations,
    translate_metadata,
)

__all__ = [
    "DEFAULT_LANGUAGES",
    "LOCALE_MAP",
    "TranslationResult",
    "korean_to_locale",
    "to_youtube_localizations",
    "translate_metadata",
]
