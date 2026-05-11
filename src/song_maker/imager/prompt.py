"""곡 메타데이터 → 이미지 프롬프트 변환."""

from song_maker.models import Song

GENRE_VISUAL_MAP = {
    "발라드": "soft watercolor landscape, pastel tones",
    "K-pop": "neon lights cityscape, vibrant pop art",
    "힙합": "urban street art, graffiti style, bold colors",
    "인디": "warm analog film photography, natural scenery",
    "댄스": "abstract geometric shapes, electric colors",
    "R&B": "night city skyline, warm ambient lighting",
    "록": "dramatic storm clouds, high contrast",
    "트로트": "traditional korean scenery, autumn colors",
    "팝": "colorful abstract art, modern design",
}

MOOD_VISUAL_MAP = {
    "밝은": "bright, sunny, warm golden light",
    "슬픈": "rainy, misty, cool blue tones",
    "몽환적": "dreamy, ethereal, soft focus, glowing",
    "에너지틱": "dynamic, explosive, high energy particles",
    "잔잔한": "calm lake, serene, gentle morning light",
    "어두운": "dark, moody, deep shadows, dramatic",
}


def build_image_prompt(song: Song) -> str:
    """배경 이미지 프롬프트 생성. custom_image_prompt 있으면 그것 우선."""
    if song.custom_image_prompt:
        return song.custom_image_prompt

    # direct 모드(시트): suno_title/suno_tags 기반
    if song.suno_title and song.suno_tags:
        return (
            f"Album cover art for a song titled '{song.suno_title}'. "
            f"Style cues: {song.suno_tags}. "
            f"Cinematic wide shot, 16:9 aspect ratio, no text, no people, "
            f"high quality, evocative and modern."
        )

    # 기존 대화형 모드
    genre_style = GENRE_VISUAL_MAP.get(song.genre, "abstract art")
    mood_style = MOOD_VISUAL_MAP.get(song.mood, "atmospheric")

    return (
        f"{mood_style} {genre_style} inspired by the theme '{song.theme}'. "
        f"Cinematic wide shot, 16:9 aspect ratio, no text, no people, "
        f"high quality, suitable for music video background."
    )


def build_thumbnail_prompt(song: Song) -> str:
    """썸네일 프롬프트 생성. direct 모드일 땐 suno_title 사용."""
    title_text = song.suno_title or song.theme
    mood_style = MOOD_VISUAL_MAP.get(song.mood, "atmospheric")

    return (
        f"YouTube music video thumbnail. "
        f"Bold stylized text '{title_text}' centered. "
        f"{mood_style} style. "
        f"Eye-catching, vibrant colors, 16:9 aspect ratio."
    )
