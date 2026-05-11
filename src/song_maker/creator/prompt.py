"""사용자 입력 → Suno 프롬프트 변환.

Suno 모드 구분:
- Simple (/api/generate): gpt_description_prompt에 설명문 → Suno가 가사+음악 자동 생성
- Advanced (/api/custom_generate): prompt에 실제 가사, tags에 스타일, title에 제목
"""

from song_maker.models import SongRequest

SUNO_MODEL = "chirp-fenix"  # Suno v5.5

GENRE_TAG_MAP = {
    "발라드": "ballad, emotional, piano",
    "K-pop": "kpop, catchy, upbeat",
    "힙합": "hiphop, rap, beat",
    "인디": "indie, acoustic, mellow",
    "댄스": "dance, edm, electronic",
    "R&B": "rnb, soul, groove",
    "록": "rock, guitar, band",
    "트로트": "trot, traditional korean",
    "팝": "pop, catchy, melodic",
    "CCM": "ccm, worship, gospel, contemporary christian",
    "찬양": "worship, praise, hymn, gospel",
    "로파이": "lofi, chill, lo-fi beats",
    "재즈": "jazz, smooth, swing",
    "클래식": "classical, orchestral, symphonic",
}

MOOD_TAG_MAP = {
    "밝은": "bright, cheerful, happy",
    "슬픈": "sad, melancholy, emotional",
    "몽환적": "dreamy, ethereal, atmospheric",
    "에너지틱": "energetic, powerful, dynamic",
    "잔잔한": "calm, peaceful, gentle",
    "어두운": "dark, moody, intense",
    "희망적인": "hopeful, uplifting, inspiring",
    "경배하는": "worshipful, reverent, devotional",
    "희망적이고 경배하는": "hopeful, uplifting, worshipful, reverent",
    "웅장한": "grand, epic, majestic",
    "따뜻한": "warm, comforting, tender",
}


def _map_tags(genre: str, mood: str) -> str:
    """장르 + 분위기를 영문 태그 문자열로 변환."""
    genre_tags = GENRE_TAG_MAP.get(genre, genre.lower())
    mood_tags = MOOD_TAG_MAP.get(mood, mood.lower())
    return f"{genre_tags}, {mood_tags}"


def build_description_prompt(request: SongRequest) -> str:
    """Simple 모드용 설명문 생성. Suno가 이걸 읽고 가사+음악을 자동 생성."""
    desc = f"A {request.mood} {request.genre} song about {request.theme}"
    if request.lyrics_keywords:
        desc += f". Keywords: {', '.join(request.lyrics_keywords)}"
    return desc


def build_simple_prompt(request: SongRequest) -> dict:
    """Simple 모드 (/api/generate) 요청 바디.

    가사 키워드가 없거나 가사를 Suno에게 맡길 때 사용.
    prompt → gpt_description_prompt로 전달됨.
    """
    return {
        "prompt": build_description_prompt(request),
        "make_instrumental": False,
        "wait_audio": False,
        "model": SUNO_MODEL,
    }


def build_custom_prompt(request: SongRequest, lyrics: str) -> dict:
    """Advanced 모드 (/api/custom_generate) 요청 바디.

    직접 작성한 가사를 prompt에 넣음. tags와 title로 스타일/제목 지정.
    """
    tags = _map_tags(request.genre, request.mood)
    return {
        "prompt": lyrics,
        "tags": tags,
        "title": request.theme,
        "make_instrumental": False,
        "wait_audio": False,
        "model": SUNO_MODEL,
    }


def build_lyrics_prompt(request: SongRequest) -> str:
    """Suno /api/generate_lyrics에 보낼 가사 생성 프롬프트."""
    parts = [f"A {request.mood} {request.genre} song about {request.theme}."]
    if request.lyrics_keywords:
        parts.append(f"Include these themes: {', '.join(request.lyrics_keywords)}.")
    return " ".join(parts)


def build_direct_prompt(
    title: str,
    lyrics: str,
    tags: str,
    persona_id: str | None = None,
    make_instrumental: bool = False,
) -> dict:
    """시트에서 받은 데이터를 Suno custom_generate에 그대로 주입.

    Suno wrapper(`gcui-art/suno-api`) /api/custom_generate 페이로드.
    persona_id는 일관된 보컬 톤을 원할 때.
    """
    body: dict = {
        "prompt": lyrics,
        "tags": tags,
        "title": title,
        "make_instrumental": make_instrumental,
        "wait_audio": False,
        "model": SUNO_MODEL,
    }
    if persona_id:
        body["persona_id"] = persona_id
    return body
