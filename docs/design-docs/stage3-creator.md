# Stage 3 — Suno 곡 생성 상세 설계

## 1. 목적

사용자의 `SongRequest`를 Suno AI가 이해하는 프롬프트로 변환하고, API를 호출하여 곡을 생성하고, 오디오 파일과 가사를 다운로드한다.

---

## 2. 모듈 구성

```
creator/
├── __init__.py
├── prompt.py       # SongRequest → Suno 프롬프트 변환
└── suno.py         # Suno API 호출, 폴링, 다운로드
```

---

## 3. prompt.py 상세

### 프롬프트 변환 전략

두 가지 모드:

**모드 A — 자동 가사 (기본)**
```python
def build_suno_prompt(request: SongRequest) -> dict:
    style_tags = map_genre_mood(request.genre, request.mood)
    description = f"{request.theme}에 대한 {request.mood} {request.genre} 곡"

    return {
        "prompt": description,
        "tags": style_tags,
        "make_instrumental": False,
        "wait_audio": False
    }
```

**모드 B — 커스텀 가사 (키워드 제공 시)**
```python
def build_suno_prompt_with_lyrics(request: SongRequest) -> dict:
    lyrics_hint = ", ".join(request.lyrics_keywords)
    prompt = f"[주제: {request.theme}] [키워드: {lyrics_hint}]"

    return {
        "prompt": prompt,
        "tags": map_genre_mood(request.genre, request.mood),
        "title": request.theme,
        "make_instrumental": False,
        "wait_audio": False
    }
```

### 장르/분위기 → 영문 태그 매핑

```python
GENRE_TAG_MAP = {
    "발라드": "ballad, emotional, piano",
    "K-pop": "kpop, catchy, upbeat",
    "힙합": "hiphop, rap, beat",
    "인디": "indie, acoustic, mellow",
    "댄스": "dance, edm, electronic",
    "R&B": "rnb, soul, groove",
    "록": "rock, guitar, band",
    "트로트": "trot, traditional korean",
}

MOOD_TAG_MAP = {
    "밝은": "bright, cheerful, happy",
    "슬픈": "sad, melancholy, emotional",
    "몽환적": "dreamy, ethereal, atmospheric",
    "에너지틱": "energetic, powerful, dynamic",
    "잔잔한": "calm, peaceful, gentle",
    "어두운": "dark, moody, intense",
}
```

---

## 4. suno.py 상세

### 연동 방식

suno-api 오픈소스 래퍼를 로컬 서버로 실행하고 HTTP로 호출:

```
기본 URL: http://localhost:3000 (config.toml에서 변경 가능)
```

### 사전 조건

```
[필수] Suno 유료 계정 (Pro/Premier) — 쿠키 기반 인증
[필수] 2Captcha API Key + 잔액 — hCaptcha 자동 해결 (유료/무료 계정 무관)
[필수] Node.js 18+ — suno-api 서버 실행
[필수] Playwright + Chromium — 캡차 자동화용 브라우저
[주의] 쿠키 ~7일마다 만료 → 수동 갱신 필요
[주의] Windows에서 캡차 빈도 높음 (macOS 대비)
```

### 함수 (동기 방식)

> async를 사용하지 않는다. Typer 호환성 + 순차 파이프라인 특성상 동기 방식이 적합.
> 상세 근거: `DESIGN.md` 섹션 4 참조.

```python
def generate(prompt: dict, base_url: str) -> str:
    """곡 생성 요청 → task_id 반환. httpx.Client 동기 호출."""

def poll_status(task_id: str, base_url: str, timeout: int = 300) -> dict:
    """생성 상태 폴링 (5초 간격 time.sleep, 기본 5분 타임아웃)"""

def download(song_data: dict, output_dir: Path) -> tuple[Path, Path]:
    """오디오 + 가사 다운로드 → (audio_path, lyrics_path) 반환"""
```

### 생성 흐름

```
1. POST /api/generate  →  task_ids[] 수신
2. 폴링 루프:
   GET /api/get?ids={id}
   → status == "streaming" : 진행 중 (진행바 업데이트)
   → status == "complete"  : 완료 → 다운로드
   → status == "error"     : 실패 → 에러 처리
   → 5분 초과             : 타임아웃
3. 오디오 URL에서 MP3 다운로드 → output/{song_id}/audio.mp3
4. 가사 텍스트 추출 → output/{song_id}/lyrics.txt
```

### 진행 표시

```python
import time

with Progress() as progress:
    task = progress.add_task("곡 생성 중...", total=None)
    while not completed:
        status = poll_status(task_id, base_url)
        if status == "streaming":
            progress.update(task, description="곡 생성 중... (스트리밍)")
        time.sleep(5)
```

### 다중 곡 생성

`count > 1`인 경우 순차 생성:
```
곡 1/3 생성 중... ━━━━━━━━━━━━━━━━━━━━ 완료
곡 2/3 생성 중... ━━━━━━━━━━━━━━━━━━━━ 완료
곡 3/3 생성 중... ━━━━━━━━━━━━━━━━━━━━ 진행 중
```

---

## 5. 저장 구조

```
output/{project_name}/{song_id}/
├── meta.json       # 곡 메타데이터 + 상태
├── audio.mp3       # 오디오 파일
└── lyrics.txt      # 가사 텍스트
```

### meta.json 예시

```json
{
  "id": "a1b2c3d4",
  "status": "created",
  "genre": "발라드",
  "mood": "몽환적",
  "theme": "봄날의 설렘",
  "lyrics_keywords": ["벚꽃", "바람", "설렘"],
  "suno_task_id": "xxxx-xxxx",
  "audio_path": "audio.mp3",
  "lyrics_path": "lyrics.txt",
  "created_at": "2026-03-31T10:01:30"
}
```

---

## 6. Suno API 실패 시 대안 경로

suno-api는 비공식 래퍼로 500 에러, 쿠키 만료, 서버 중단이 빈번하다.
Suno API가 실패할 경우를 대비한 대안 경로:

### 대안 A — 수동 MP3 임포트

```bash
songmaker import <mp3_path> --genre "발라드" --mood "몽환적" --theme "봄날의 설렘"
```

- 사용자가 Suno 웹사이트에서 직접 곡을 생성/다운로드
- `songmaker import`로 MP3 파일을 output/에 등록
- Stage 4 (이미지 생성)부터 파이프라인 재개
- meta.json에 `source: "manual_import"` 기록

### 대안 B — 서드파티 API 전환

```toml
# config.toml
[suno]
provider = "sunoapi.org"          # "local" (기본) 또는 "sunoapi.org"
api_url = "https://api.sunoapi.org"
api_key = ""
```

- `suno.py` 내부에서 provider 설정에 따라 호출 대상 전환
- 인터페이스(generate, poll_status, download)는 동일하게 유지

### 대안 C — 다른 AI 음악 서비스

추후 Udio, MusicGen 등 다른 서비스가 API를 제공할 경우:
- `creator/` 디렉토리에 새 모듈 추가 (예: `udio.py`)
- `config.toml`에서 `[creator].engine = "udio"` 설정
- `cli.py`에서 엔진 설정에 따라 모듈 선택

### CLI 명령어 추가

```bash
songmaker import <mp3_path> [options]   # 수동 MP3 임포트
  --genre       장르
  --mood        분위기
  --theme       주제
  --lyrics      가사 파일 경로 (선택)
  --project     프로젝트 이름 (선택)
```

---

## 7. Gate 3 검증 연계

이 Stage 완료 후 Gate 3이 실행된다:
- API 응답 수신 (task_id)
- 생성 완료 (status == complete)
- audio.mp3 존재 + 크기 > 100KB
- 오디오 무결성 (ffprobe)
- lyrics.txt 존재 (비차단)

Gate 3 통과 시 → Stage 4 (이미지 생성)로 진행.
