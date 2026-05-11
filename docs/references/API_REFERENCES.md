# Song Maker — API References

## 1. YouTube Data API v3

### 트렌드 조회

```
GET https://www.googleapis.com/youtube/v3/videos
```

| 파라미터 | 값 | 설명 |
|----------|-----|------|
| `part` | `snippet,statistics` | 제목/태그 + 조회수 |
| `chart` | `mostPopular` | 인기 차트 |
| `regionCode` | `KR` | 지역 |
| `videoCategoryId` | `10` | Music 카테고리 |
| `maxResults` | `20` | 조회 수 |
| `key` | API Key | 인증 |

**공식 문서**: https://developers.google.com/youtube/v3/docs/videos/list

### 영상 업로드

```
POST https://www.googleapis.com/upload/youtube/v3/videos
```

| 파라미터 | 값 | 설명 |
|----------|-----|------|
| `part` | `snippet,status` | 메타데이터 + 공개 설정 |
| `uploadType` | `resumable` | 이어받기 업로드 |

**인증**: OAuth 2.0 (scope: `youtube.upload`)
**공식 문서**: https://developers.google.com/youtube/v3/docs/videos/insert

### 할당량

| 작업 | 비용 (유닛) |
|------|------------|
| videos.list | 1 |
| videos.insert | 1600 |
| thumbnails.set | 50 |
| 일일 한도 | 10,000 |

---

## 2. Suno API (서드파티)

### suno-api 오픈소스 래퍼

**GitHub**: https://github.com/gcui-art/suno-api

로컬 서버로 실행 후 REST API 호출:

```
기본 URL: http://localhost:3000
```

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/api/generate` | POST | 곡 생성 요청 |
| `/api/get?ids={id}` | GET | 생성 상태 조회 |
| `/api/get_limit` | GET | 남은 크레딧 조회 |

### 곡 생성 요청 바디

```json
{
  "prompt": "A dreamy spring ballad about cherry blossoms",
  "make_instrumental": false,
  "wait_audio": false
}
```

### 커스텀 가사 모드

```json
{
  "prompt": "[Verse]\n벚꽃이 흩날리는 봄날...\n[Chorus]\n...",
  "tags": "ballad, dreamy, spring",
  "title": "봄날의 설렘",
  "make_instrumental": false,
  "wait_audio": false
}
```

---

## 3. Gemini Image API

### SDK 설치

```bash
pip install google-genai
```

### 이미지 생성

```python
from google import genai
from google.genai import types

client = genai.Client(api_key="YOUR_API_KEY")

# 방법 1: generate_content (기존 방식, 동작 확인됨)
response = client.models.generate_content(
    model="gemini-3.1-flash-image-preview",
    contents="A dreamy spring landscape with cherry blossoms, 16:9, cinematic",
    config=types.GenerateContentConfig(
        response_modalities=["IMAGE"],   # 반드시 대문자
    ),
)

for part in response.parts:
    if part.inline_data:
        image_bytes = part.inline_data.data

# 방법 2: Interactions API (신규 방식)
import base64

interaction = client.interactions.create(
    model="gemini-3.1-flash-image-preview",
    input="A dreamy spring landscape with cherry blossoms, 16:9, cinematic",
    response_modalities=["IMAGE"],
)

for output in interaction.outputs:
    if output.type == "image":       # 응답 확인 시에는 소문자
        with open("output.png", "wb") as f:
            f.write(base64.b64decode(output.data))
```

> **주의**: `response_modalities`는 **대문자** (`"IMAGE"`)를 사용해야 한다.
> 소문자 `"image"`를 쓰면 이미지가 생성되지 않는다.

### 모델 옵션

| 모델 ID | 특징 | 가격 |
|---------|------|------|
| `gemini-3.1-flash-image-preview` | 최신, 4K, 빠름 | $0.045/장 |
| `gemini-3-pro-image-preview` | 고품질, 복잡한 지시 | $0.134/장 |
| `imagen-4` | 이미지 전용, 가성비 | $0.02~0.06/장 |

**공식 문서**: https://ai.google.dev/gemini-api/docs/image-generation

### 무료 할당량

- Google AI Studio: 하루 500장
- API Key 방식: 분당 60요청, 하루 1500요청

---

## 4. FFmpeg

### 기본 렌더링 명령어

```bash
ffmpeg -loop 1 -i background.png -i audio.mp3 \
  -c:v libx264 -tune stillimage \
  -c:a aac -b:a 192k \
  -pix_fmt yuv420p \
  -shortest \
  output.mp4
```

### 자막 포함

```bash
# 시스템 기본 폰트 사용 (FontName 생략)
ffmpeg -loop 1 -i background.png -i audio.mp3 \
  -vf "subtitles=lyrics.srt:force_style='FontSize=24'" \
  -c:v libx264 -c:a aac -b:a 192k \
  -pix_fmt yuv420p -shortest \
  output.mp4

# 특정 폰트 지정 (한글 자막 깨짐 방지)
# Windows: Malgun Gothic / macOS: AppleGothic / Linux: NanumGothic
ffmpeg -loop 1 -i background.png -i audio.mp3 \
  -vf "subtitles=lyrics.srt:force_style='FontName=Malgun Gothic,FontSize=24'" \
  -c:v libx264 -c:a aac -b:a 192k \
  -pix_fmt yuv420p -shortest \
  output.mp4
```

### 페이드 효과

```bash
# 페이드인 3초, 페이드아웃 3초 (영상 끝 기준)
-vf "fade=t=in:st=0:d=3,fade=t=out:st={duration-3}:d=3"
-af "afade=t=in:st=0:d=3,afade=t=out:st={duration-3}:d=3"
```

**공식 문서**: https://ffmpeg.org/documentation.html
