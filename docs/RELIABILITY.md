# Song Maker — Reliability Guide

## 1. 파이프라인 안정성

### 중간 실패 복구

각 Stage 완료 시 `meta.json`에 상태를 기록한다. 중간에 실패하면 마지막 성공 Stage부터 재실행 가능.

```
Song 상태 흐름:
created → imaged → rendered → uploaded
```

| 실패 지점 | 복구 방법 |
|-----------|-----------|
| Stage 3 (곡 생성) 실패 | `songmaker create` 재실행 |
| Stage 4 (이미지) 실패 | `songmaker image <song_id>` 재실행 |
| Stage 5 (렌더링) 실패 | `songmaker render <song_id>` 재실행 |
| Stage 6 (업로드) 실패 | `songmaker upload <song_id>` 재실행 |

### 상태 파일 구조

```json
{
  "id": "a1b2c3",
  "status": "imaged",
  "genre": "발라드",
  "mood": "몽환적",
  "theme": "봄날의 설렘",
  "created_at": "2026-03-31T10:00:00",
  "audio_path": "audio.mp3",
  "background_path": "background.png",
  "video_path": null,
  "youtube_url": null
}
```

---

## 2. API 호출 안정성

> 각 Gate별 재시도 횟수/간격의 상세 분기 흐름은 [VERIFICATION.md](VERIFICATION.md)를 참조.

### 재시도 정책

| API | 재시도 횟수 | 간격 | 비고 |
|-----|------------|------|------|
| YouTube Data API (조회) | 3회 | 1초, 2초, 4초 (지수 백오프) | 429 Rate Limit 시 대기 |
| Suno API | 3회 | 5초, 10초, 20초 | 생성 폴링은 별도 (5초 간격, 최대 5분) |
| Gemini Image API | 3회 | 2초, 4초, 8초 | fallback 모델로 전환 가능 |
| YouTube Data API (업로드) | 2회 | 10초 | 대용량 파일 업로드 고려 |

### 타임아웃

| 작업 | 타임아웃 |
|------|----------|
| Suno 곡 생성 대기 | 5분 |
| Gemini 이미지 생성 | 60초 |
| FFmpeg 렌더링 | 10분 |
| YouTube 업로드 | 10분 |

---

## 3. 외부 의존성 체크

`songmaker run` 실행 전 필수 의존성을 확인한다:

```
[체크 항목]
✓ Python 3.11+
✓ FFmpeg 설치 여부 (shutil.which)
✓ YouTube API Key 설정 여부
✓ Gemini API Key 설정 여부
✓ Suno 쿠키 설정 여부
✓ 2Captcha API Key 설정 여부
✓ suno-api 서버 응답 여부 (GET /api/get_limit)
✓ 2Captcha 잔액 확인 (잔액 $0이면 경고)
✓ 네트워크 연결 상태
```

미충족 항목 발견 시 구체적인 설정 안내 메시지 출력 후 종료.

---

## 4. 데이터 무결성

| 규칙 | 설명 |
|------|------|
| **원자적 저장** | 파일 저장 시 임시 파일에 먼저 쓴 후 rename (부분 기록 방지) |
| **메타 동기화** | 파일 저장과 meta.json 업데이트를 함께 수행 |
| **output 보존** | 사용자가 명시적으로 삭제하지 않는 한 output/ 파일 유지 |
