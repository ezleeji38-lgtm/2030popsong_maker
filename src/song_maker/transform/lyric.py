"""원곡 가사 → 새 가사 5규칙 변환 (Gemini 텍스트 모델).

5규칙:
1. 음절수와 띄어쓰기 그대로 유지
2. 똑같은 단어 금지 (비슷한 발음의 다른 단어로 교체)
3. '/' 그대로 유지
4. 잔잔한 발라드 감성 + 현실적
5. 저작권 안전

페르소나 메이크 자동화 시트의 J열(Song Lyric)을 채울 때 사용.
"""

from song_maker import config as cfg

PROMPT_TEMPLATE = """지금부터 너는 이시대 최고의 작사가야. 지금부터 작사를 할건데, 다음의 가사를 참고해서 만들어줘.

[참고 가사]
{original_lyrics}

여기에 나는 제목을 '{new_title}' 로 하고싶고 내용은 '{new_subject}' 로 하고싶어.

잘 바꿔주면 되는데 단! 주의할 것이 몇가지 있어.

첫번째, 위의 예시 가사와 음절수와 띄어쓰기를 반드시 똑같이 해줘
두번째, 절대 똑같은 단어가 들어가면 안돼! 꼭 다른 비슷한 발음의 단어로 바꿔줘야해.
세번째, '/' 도 그대로 써서 만들어줘
네번째, 잔잔한 감성의 발라드 가사이기 때문에 전체적으로 감성적이면서 현실적으로 써줘야 해
다섯번째, 반드시 저작권 문제 없이 만들어 줘야해~!

규칙을 모두 지킨 변환된 가사만 출력해. 부가 설명이나 마크다운 헤더 없이 가사 본문만."""


def transform_lyrics(
    config: dict,
    original_lyrics: str,
    new_title: str,
    new_subject: str,
) -> str:
    """원곡 가사를 새 제목·내용에 맞춰 5규칙으로 변환.

    Args:
        config: 전역 config (Gemini key + model)
        original_lyrics: 참고 원곡 가사 (페르소나 메이크 자동화 G열)
        new_title: 새 영어 제목 (C열)
        new_subject: 새 가사 내용 한국어 설명 (E열)

    Returns:
        변환된 가사 (J열에 들어갈 텍스트)

    Raises:
        RuntimeError: Gemini 키 미설정, 응답 비어있음, 429 RESOURCE_EXHAUSTED
    """
    from google import genai

    api_key = cfg.get(config, "gemini", "api_key")
    if not api_key:
        raise RuntimeError("Gemini API 키 미설정 — `songmaker config` 실행 후 등록")

    text_model = cfg.get(config, "gemini", "text_model") or "gemini-3-flash-preview"
    fallback = cfg.get(config, "gemini", "text_fallback_model") or "gemini-2.5-flash"

    prompt = PROMPT_TEMPLATE.format(
        original_lyrics=original_lyrics.strip(),
        new_title=new_title.strip(),
        new_subject=new_subject.strip(),
    )

    client = genai.Client(api_key=api_key)

    last_err: Exception | None = None
    for attempt_model in [text_model, fallback]:
        if not attempt_model:
            continue
        try:
            response = client.models.generate_content(
                model=attempt_model,
                contents=prompt,
            )
            text = getattr(response, "text", None)
            if text and text.strip():
                return text.strip()
            raise RuntimeError(f"{attempt_model}: 응답이 비어있음")
        except Exception as e:
            last_err = e
            err_str = str(e)
            if "RESOURCE_EXHAUSTED" in err_str or "429" in err_str:
                raise RuntimeError(
                    "Gemini 무료 일 한도 초과 (429 RESOURCE_EXHAUSTED).\n"
                    "  → 24시간 후 재시도 또는 유료 결제 활성화.\n"
                    f"  원본: {err_str[:200]}"
                ) from e
            if attempt_model == fallback:
                break
            continue

    raise RuntimeError(f"가사 변환 실패: {last_err}")
