# Data Schema

> Song Maker는 데이터베이스를 사용하지 않는다. JSON 파일 기반 저장.
> 이 문서는 `meta.json` 파일의 스키마를 정의한다.

---

## 1. Project meta.json

위치: `output/{project_name}/meta.json`

```json
{
  "name": "spring_ballads",
  "created_at": "2026-03-31T10:00:00",
  "songs": ["a1b2c3d4", "e5f6g7h8"]
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `name` | string | 프로젝트 이름 |
| `created_at` | datetime | 생성 시간 |
| `songs` | list[string] | 곡 ID 목록 |

---

## 2. Song meta.json

위치: `output/{project_name}/song_{id}/meta.json`

```json
{
  "id": "a1b2c3d4",
  "genre": "발라드",
  "mood": "몽환적",
  "theme": "봄날의 설렘",
  "lyrics_keywords": ["벚꽃", "바람"],
  "reference_song": "Spring Breeze",
  "status": "uploaded",
  "audio_path": "audio.mp3",
  "lyrics_path": "lyrics.txt",
  "background_path": "background.png",
  "thumbnail_path": "thumbnail.png",
  "video_path": "video.mp4",
  "youtube_url": "https://youtu.be/xxxxx",
  "image_model": "gemini-3.1-flash-image-preview",
  "image_prompt": "dreamy soft watercolor landscape...",
  "render_options": {
    "resolution": "1920x1080",
    "fade": 2,
    "subtitles": true
  },
  "gates": {
    "gate1": {
      "passed": true,
      "timestamp": "2026-03-31T10:00:01",
      "checks": [
        {"name": "api_response", "passed": true, "blocking": true},
        {"name": "result_count", "passed": true, "blocking": true}
      ]
    },
    "gate3": { "..." : "..." },
    "gate4": { "..." : "..." },
    "gate5": { "..." : "..." },
    "gate6": { "..." : "..." }
  },
  "created_at": "2026-03-31T10:00:00",
  "uploaded_at": "2026-03-31T10:05:00"
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | UUID |
| `genre` | string | 장르 |
| `mood` | string | 분위기 |
| `theme` | string | 주제 |
| `lyrics_keywords` | list[string] | 가사 키워드 |
| `reference_song` | string? | 참고곡 |
| `status` | string | created / imaged / rendered / uploaded |
| `audio_path` | string? | 오디오 상대 경로 |
| `lyrics_path` | string? | 가사 상대 경로 |
| `background_path` | string? | 배경 이미지 상대 경로 |
| `thumbnail_path` | string? | 썸네일 상대 경로 |
| `video_path` | string? | 영상 상대 경로 |
| `youtube_url` | string? | YouTube URL |
| `image_model` | string? | 사용된 Gemini 모델 |
| `image_prompt` | string? | 사용된 이미지 프롬프트 |
| `render_options` | object? | 렌더링 옵션 |
| `gates` | object | Gate 검증 이력 |
| `created_at` | datetime | 생성 시간 |
| `uploaded_at` | datetime? | 업로드 시간 |

---

## 3. 상태 전이

```
created  →  imaged  →  rendered  →  uploaded
(Stage 3)   (Stage 4)   (Stage 5)   (Stage 6)
```

각 상태 전이는 해당 Gate 검증 통과 후 발생한다.
