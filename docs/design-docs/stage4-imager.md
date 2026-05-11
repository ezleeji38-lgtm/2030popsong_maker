# Stage 4 — Gemini 이미지 생성 상세 설계

## 1. 목적

곡의 메타데이터(장르, 분위기, 주제)를 기반으로 Gemini AI에 이미지 프롬프트를 생성하고, 배경 이미지와 썸네일을 자동 생성한다.

---

## 2. 모듈 구성

```
imager/
├── __init__.py
├── prompt.py       # 곡 메타 → 이미지 프롬프트 변환
└── gemini.py       # Gemini API 호출, 이미지 저장
```

---

## 3. prompt.py 상세

### 배경 이미지 프롬프트

```python
def build_image_prompt(song: Song) -> str:
    """곡 메타데이터 → 배경 이미지 프롬프트"""
    genre_style = GENRE_VISUAL_MAP.get(song.genre, "abstract art")
    mood_style = MOOD_VISUAL_MAP.get(song.mood, "atmospheric")

    return (
        f"{mood_style} {genre_style} inspired by the theme '{song.theme}'. "
        f"Cinematic wide shot, 16:9 aspect ratio, no text, no people, "
        f"high quality, suitable for music video background."
    )
```

### 썸네일 프롬프트

```python
def build_thumbnail_prompt(song: Song) -> str:
    """곡 메타데이터 → 썸네일 프롬프트"""
    return (
        f"YouTube music video thumbnail. "
        f"Bold stylized text '{song.theme}' centered. "
        f"{MOOD_VISUAL_MAP.get(song.mood, 'atmospheric')} style. "
        f"Eye-catching, vibrant colors, 16:9 aspect ratio."
    )
```

### 시각 스타일 매핑

```python
GENRE_VISUAL_MAP = {
    "발라드": "soft watercolor landscape, pastel tones",
    "K-pop": "neon lights cityscape, vibrant pop art",
    "힙합": "urban street art, graffiti style, bold colors",
    "인디": "warm analog film photography, natural scenery",
    "댄스": "abstract geometric shapes, electric colors",
    "R&B": "night city skyline, warm ambient lighting",
    "록": "dramatic storm clouds, high contrast",
    "트로트": "traditional korean scenery, autumn colors",
}

MOOD_VISUAL_MAP = {
    "밝은": "bright, sunny, warm golden light",
    "슬픈": "rainy, misty, cool blue tones",
    "몽환적": "dreamy, ethereal, soft focus, glowing",
    "에너지틱": "dynamic, explosive, high energy particles",
    "잔잔한": "calm lake, serene, gentle morning light",
    "어두운": "dark, moody, deep shadows, dramatic",
}
```

---

## 4. gemini.py 상세

### SDK 초기화

```python
from google import genai
from google.genai import types

def get_client(api_key: str) -> genai.Client:
    return genai.Client(api_key=api_key)
```

### 이미지 생성

```python
def generate_image(
    client: genai.Client,
    prompt: str,
    output_path: Path,
    model: str = "gemini-3.1-flash-image-preview"
) -> Path:
    """동기 함수. Gemini SDK는 내부적으로 동기 HTTP 호출."""
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],   # 반드시 대문자
        ),
    )

    for part in response.parts:
        if part.inline_data:
            output_path.write_bytes(part.inline_data.data)
            return output_path

    raise ImageGenerationError("이미지 데이터가 응답에 없습니다.")
```

> **참고**: `response_modalities`는 반드시 대문자 `"IMAGE"`를 사용한다.
> 소문자 `"image"`를 쓰면 이미지가 생성되지 않는다.

### Fallback 전략

```
1차 시도: gemini-3.1-flash-image-preview (빠름, 저렴)
    ↓ 실패
2차 시도: gemini-3-pro-image-preview (고품질)
    ↓ 실패
3차 시도: 프롬프트 단순화 후 1차 모델 재시도
    ↓ 실패
사용자 판단: 직접 이미지 지정 / 기본 배경 / 중단
```

### 생성 흐름

```
1. build_image_prompt(song) → 배경 프롬프트
2. generate_image(prompt, background.png) → 배경 저장
3. build_thumbnail_prompt(song) → 썸네일 프롬프트
4. generate_image(prompt, thumbnail.png) → 썸네일 저장
5. Gate 4 검증 실행
```

### 다중 곡 이미지 생성

곡마다 독립 실행. 실패한 곡만 재시도:
```
곡 1/3 이미지 생성... ━━━━━━━━━━━━━━━━━━━━ 완료
곡 2/3 이미지 생성... ━━━━━━━━━━━━━━━━━━━━ 실패 → 재시도
곡 2/3 이미지 재생성... ━━━━━━━━━━━━━━━━━━ 완료
곡 3/3 이미지 생성... ━━━━━━━━━━━━━━━━━━━━ 완료
```

---

## 5. 저장 구조

```
output/{project_name}/{song_id}/
├── meta.json
├── audio.mp3
├── lyrics.txt
├── background.png      ← 배경 이미지
└── thumbnail.png       ← 썸네일 이미지
```

meta.json 업데이트:
```json
{
  "status": "imaged",
  "background_path": "background.png",
  "thumbnail_path": "thumbnail.png",
  "image_model": "gemini-3.1-flash-image-preview",
  "image_prompt": "dreamy soft watercolor landscape..."
}
```

---

## 6. Gate 4 검증 연계

이 Stage 완료 후 Gate 4가 실행된다:
- API 응답 + 이미지 데이터 존재
- background.png 존재 + 크기 > 10KB
- PNG 디코딩 가능
- 해상도 >= 1920x1080 (비차단)
- thumbnail.png 존재 (비차단, 실패 시 배경 복사)

Gate 4 통과 시 → Stage 5 (렌더링)로 진행.
