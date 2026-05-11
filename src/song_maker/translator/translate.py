"""Gemini로 YouTube 제목/설명을 다국어 번역.

JS 원본(@google/genai)의 동작을 google-genai Python SDK로 포팅.
- responseMimeType: application/json
- responseSchema: 배열 of {language, translatedTitle, translatedDescription}
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable

# 원본 JS의 languages 문자열에서 추출 가능한 언어들 (클립보드 복사 중 일부 누락).
# 사용자가 정확한 50개 리스트 공유하면 이 리스트를 갱신.
# 일단 보이는 것 + 일반적 YouTube locale 추가로 50개 가까이 채움.
DEFAULT_LANGUAGES: list[str] = [
    # JS 코드에서 명확히 보이는 항목
    "광둥어 (홍콩)",
    "그린란드어",
    "네덜란드어 (네덜란드)",
    "네덜란드어 (벨기에)",
    "노르웨이어",
    "덴마크어",
    "독일어 (독일)",
    "독일어 (스위스)",
    "독일어 (오스트리아)",
    "러시아어",
    "루마니아어",
    "말레이어",
    "베트남어",
    "벵골어 (인도)",
    "스웨덴어",
    "스페인어 (멕시코)",
    "스페인어 (라틴 아메리카)",
    "스페인어 (스페인)",
    "아랍어",
    "히브리어",
    "아프리칸스어",
    "아이슬란드어",
    "카탈로니아어",
    "슬로바키아어",
    "핀란드어",
    "크로아티아어",
    # 추가로 추정한 항목 (사용자가 50개 정확히 알려주면 갱신)
    "영어 (미국)",
    "영어 (영국)",
    "일본어",
    "중국어 (간체)",
    "중국어 (번체)",
    "프랑스어 (프랑스)",
    "프랑스어 (캐나다)",
    "포르투갈어 (브라질)",
    "포르투갈어 (포르투갈)",
    "이탈리아어",
    "터키어",
    "폴란드어",
    "체코어",
    "헝가리어",
    "그리스어",
    "힌디어",
    "태국어",
    "인도네시아어",
    "필리핀어",
    "우크라이나어",
    "불가리아어",
    "세르비아어",
    "에스토니아어",
    "라트비아어",
]

# 한국어 언어명 → YouTube locale 코드 매핑 (videos.localizations API용)
LOCALE_MAP: dict[str, str] = {
    "광둥어 (홍콩)": "zh-HK",
    "그린란드어": "kl",
    "네덜란드어 (네덜란드)": "nl-NL",
    "네덜란드어 (벨기에)": "nl-BE",
    "노르웨이어": "no",
    "덴마크어": "da",
    "독일어 (독일)": "de-DE",
    "독일어 (스위스)": "de-CH",
    "독일어 (오스트리아)": "de-AT",
    "러시아어": "ru",
    "루마니아어": "ro",
    "말레이어": "ms",
    "베트남어": "vi",
    "벵골어 (인도)": "bn-IN",
    "스웨덴어": "sv",
    "스페인어 (멕시코)": "es-MX",
    "스페인어 (라틴 아메리카)": "es-419",
    "스페인어 (스페인)": "es-ES",
    "아랍어": "ar",
    "히브리어": "he",
    "아프리칸스어": "af",
    "아이슬란드어": "is",
    "카탈로니아어": "ca",
    "슬로바키아어": "sk",
    "핀란드어": "fi",
    "크로아티아어": "hr",
    # 추가
    "영어 (미국)": "en",
    "영어 (영국)": "en-GB",
    "일본어": "ja",
    "중국어 (간체)": "zh-CN",
    "중국어 (번체)": "zh-TW",
    "프랑스어 (프랑스)": "fr",
    "프랑스어 (캐나다)": "fr-CA",
    "포르투갈어 (브라질)": "pt-BR",
    "포르투갈어 (포르투갈)": "pt-PT",
    "이탈리아어": "it",
    "터키어": "tr",
    "폴란드어": "pl",
    "체코어": "cs",
    "헝가리어": "hu",
    "그리스어": "el",
    "힌디어": "hi",
    "태국어": "th",
    "인도네시아어": "id",
    "필리핀어": "fil",
    "우크라이나어": "uk",
    "불가리아어": "bg",
    "세르비아어": "sr",
    "에스토니아어": "et",
    "라트비아어": "lv",
}


@dataclass
class TranslationResult:
    language: str  # 한국어 언어명 (모델 응답 그대로)
    translated_title: str
    translated_description: str

    @property
    def locale(self) -> str:
        """YouTube videos.localizations에 쓸 BCP-47 locale 코드."""
        return korean_to_locale(self.language)


def korean_to_locale(korean_name: str) -> str:
    """한국어 언어명 → BCP-47 locale 코드. 미매핑이면 'und'."""
    return LOCALE_MAP.get(korean_name.strip(), "und")


_RESPONSE_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "language": {"type": "STRING"},
            "translatedTitle": {"type": "STRING"},
            "translatedDescription": {"type": "STRING"},
        },
        "required": ["language", "translatedTitle", "translatedDescription"],
    },
}


def _build_prompt(title: str, description: str, languages: list[str]) -> str:
    """JS 원본 prompt 그대로 재현."""
    languages_str = ", ".join(languages)
    return f"""
You are a professional translator specializing in localizing YouTube content.
Objective: Translate the provided Korean YouTube title and description into the {len(languages)} languages/locales listed below.

Languages to Translate Into:
{languages_str}

RULE 1: TITLE (MAX 100 CHARS)
- If the translated title is > 100 chars, summarize it first.
- Preserve '[playlist]' tag.

RULE 2: DESCRIPTION
- Translate hashtags (e.g., #여름 -> #summer). Keep numbers (e.g., #7080).
- Keep original Emojis.
- DO NOT TRANSLATE timestamps and song titles. Keep them at the end.
- Keep natural English phrases (e.g., 'Press Play').

Content:
Title: {title}
Description: {description}
""".strip()


def translate_metadata(
    title: str,
    description: str,
    *,
    api_key: str,
    languages: Iterable[str] | None = None,
    model: str = "gemini-3-flash-preview",
    fallback_model: str = "gemini-2.5-flash",
) -> list[TranslationResult]:
    """제목/설명을 다국어로 번역. JSON 스키마 강제로 신뢰도 ↑.

    Args:
        title: 한국어(또는 원어) YouTube 제목
        description: 본문
        api_key: Gemini API 키
        languages: 번역 대상 언어 한국어명 리스트 (기본: DEFAULT_LANGUAGES)
        model: 우선 모델 (gemini-3-flash-preview)
        fallback_model: 우선 모델 실패 시 폴백

    Returns:
        TranslationResult 리스트
    """
    from google import genai
    from google.genai import types

    langs = list(languages or DEFAULT_LANGUAGES)
    prompt = _build_prompt(title, description, langs)

    client = genai.Client(api_key=api_key)
    cfg = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=_RESPONSE_SCHEMA,
    )

    last_err: Exception | None = None
    for attempt_model in [model, fallback_model]:
        if not attempt_model:
            continue
        try:
            response = client.models.generate_content(
                model=attempt_model,
                contents=prompt,
                config=cfg,
            )
            text = getattr(response, "text", None)
            if not text:
                raise RuntimeError(f"{attempt_model}: 빈 응답")
            data = json.loads(text)
            if not isinstance(data, list):
                raise RuntimeError(f"{attempt_model}: 배열 응답이 아님")
            return [
                TranslationResult(
                    language=item.get("language", ""),
                    translated_title=item.get("translatedTitle", ""),
                    translated_description=item.get("translatedDescription", ""),
                )
                for item in data
                if isinstance(item, dict)
            ]
        except Exception as e:
            last_err = e
            if attempt_model == fallback_model:
                break
            continue

    raise RuntimeError(f"번역 실패: {last_err}")


def to_youtube_localizations(results: list[TranslationResult]) -> dict[str, dict[str, str]]:
    """TranslationResult 리스트 → YouTube videos.insert localizations 형식.

    {
      "en": {"title": "...", "description": "..."},
      "ja": {"title": "...", "description": "..."},
      ...
    }
    """
    out: dict[str, dict[str, str]] = {}
    for r in results:
        loc = r.locale
        if loc == "und":
            continue
        out[loc] = {
            "title": r.translated_title[:100],
            "description": r.translated_description[:5000],
        }
    return out
