# Song Maker — System Architecture

## 1. 시스템 개요

Song Maker는 6단계 파이프라인을 순차 실행하는 CLI 도구이다.
각 Stage는 독립 모듈로 분리되어 있으며, 개별 실행 또는 전체 파이프라인 실행이 가능하다.

```
┌─────────────────────────────────────────────────────────────────┐
│                        songmaker CLI (Typer)                    │
├─────────┬──────────┬──────────┬──────────┬──────────┬──────────┤
│ Stage 1 │ Stage 2  │ Stage 3  │ Stage 4  │ Stage 5  │ Stage 6  │
│ trend/  │ (CLI     │ creator/ │ imager/  │renderer/ │uploader/ │
│         │  input)  │          │          │          │          │
├─────────┴──────────┴──────────┴──────────┴──────────┴──────────┤
│                      config.py + models.py                      │
├─────────────────────────────────────────────────────────────────┤
│              output/  (JSON 메타데이터 + 파일 저장)              │
└─────────────────────────────────────────────────────────────────┘
         │                │              │              │
    YouTube API      Suno API      Gemini API     YouTube API
    (조회)           (생성)         (이미지)        (업로드)
```

---

## 2. 모듈 구조

### 2.1 계층도

```
song_maker/
├── cli.py              ─── 진입점. Typer 앱. 23개 명령 라우팅.
├── config.py           ─── TOML 설정 로드/저장 + 환경변수 오버라이드 + chmod 600.
├── models.py           ─── 공유 데이터 모델 (Pydantic v2)
├── gates.py            ─── 검증 게이트 (Gate 1~6, Check, GateResult)
├── storage.py          ─── output_dir 동적 해결 (env > config > cwd) — cron-safe
│
├── trend/              ─── [Stage 1] 트렌드 조사 (선택 — `--with-trend`/`--skip-trend`)
│   ├── youtube.py      ─── YouTube Data API v3 호출 + verify_gate1
│   └── analyzer.py     ─── 장르/키워드 추출, top_genres/top_keywords 계산
│
├── creator/            ─── [Stage 3] 곡 생성
│   ├── suno.py         ─── Suno API 래퍼 (httpx)
│   │                       ├─ generate_song (Simple/Advanced 자동 분기)
│   │                       ├─ generate_song_direct (시트 모드: title/lyrics/tags 직접)
│   │                       ├─ get_suno_credits (GET /api/get_limit)
│   │                       ├─ _poll_until_complete (15s 간격, 10min 타임아웃)
│   │                       └─ verify_gate3 (60-360s 차단, 180-210s 권장 비차단)
│   └── prompt.py       ─── 사용자 입력 → Suno 프롬프트 변환 (build_simple/custom/direct)
│
├── imager/             ─── [Stage 4] 이미지 생성
│   ├── gemini.py       ─── google-genai SDK (모델: gemini-2.5-flash-image)
│   │                       ├─ 배경 1920x1080 + 썸네일 1280x720
│   │                       ├─ 429 RESOURCE_EXHAUSTED 친절 메시지
│   │                       ├─ fallback_model 자동 전환
│   │                       └─ verify_gate4 (파일·크기·디코딩·해상도)
│   └── prompt.py       ─── 곡 메타데이터 → 이미지 프롬프트 (build_image/thumbnail)
│
├── renderer/           ─── [Stage 5] 영상 렌더링 (선택, CapCut 워크플로우에선 미사용)
│   └── ffmpeg.py       ─── FFmpeg subprocess + ASS 자막 burn-in
│
├── uploader/           ─── [Stage 6] YouTube 업로드 (선택, 본 운영은 수동 업로드)
│   └── youtube.py      ─── YouTube Data API v3 + OAuth 2.0
│
├── sheet/              ─── Google Sheets 통합 (Phase 1 핵심)
│   ├── client.py       ─── gspread + Service Account
│   │                       ├─ 12컬럼 스키마 (HEADERS 상수)
│   │                       ├─ verify_schema / fetch_pending_rows
│   │                       ├─ mark_processing/done/failed (batch_update — API 1회/곡)
│   │                       └─ append_pending_row (챗봇 → 시트 한 행)
│   └── parse.py        ─── 챗봇 출력 파서 (TITLE/TAGS/LYRICS/PERSONA_ID)
│                           markdown(`**`, `##`)·이모지·한국어 콜론(：) 허용
│
├── validation/         ─── 사전 검증
│   ├── lint.py         ─── 5000자 한도, 80자 제목 한도(Suno 제약), 빈 마커, [Section] 누락
│   └── duplicate.py    ─── normalize_lyrics + difflib.SequenceMatcher, 75% 임계 차단
│
├── translator/         ─── Gemini 다국어 번역 (YouTube localizations용 50개 언어)
│   └── translate.py    ─── google-genai SDK + JSON 응답 파싱
│
├── playlist/           ─── 플레이리스트 챕터 타임라인
│   └── timeline.py     ─── 곡 묶음 → YouTube 챕터 텍스트 (00:00 Song Title 형식)
│
├── capcut/             ─── CapCut 핸드오프
│   └── (inbox/outbox)  ─── mp3 + 썸네일 자동 복사, mp4 export 감지
│
└── drive/              ─── Google Drive 일별 가사 백업 (선택)
    └── client.py       ─── Service Account + Drive API v3
```

### 2.2 모듈 간 의존 관계

```
cli.py
 ├── config.py          (모든 모듈이 참조)
 ├── models.py          (모든 모듈이 참조)
 ├── gates.py           (cli.py가 각 Stage 후 호출)
 ├── trend/youtube.py   → trend/analyzer.py
 ├── creator/prompt.py  → creator/suno.py
 ├── imager/prompt.py   → imager/gemini.py
 ├── renderer/ffmpeg.py (독립)
 └── uploader/youtube.py(독립)
```

각 Stage 모듈은 서로 직접 참조하지 않는다.
`cli.py`가 오케스트레이터 역할을 하며, `models.py`의 데이터 모델을 통해 Stage 간 데이터를 전달한다.

---

## 3. 데이터 모델

### 3.1 핵심 모델

```python
# models.py (Pydantic BaseModel 사용)

class TrendItem(BaseModel):
    rank: int
    title: str
    artist: str
    view_count: int
    tags: list[str]
    video_id: str
    published_at: str

class TrendReport(BaseModel):
    region: str
    items: list[TrendItem]
    top_genres: list[str]
    top_keywords: list[str]
    fetched_at: datetime

class SongRequest(BaseModel):
    genre: str
    mood: str
    theme: str
    lyrics_keywords: list[str] = []
    reference_song: str | None = None
    count: int = 1

class Song(BaseModel):
    id: str                     # UUID
    genre: str
    mood: str
    theme: str
    lyrics_keywords: list[str] = []
    reference_song: str | None = None
    audio_path: str | None = None
    lyrics_path: str | None = None
    background_path: str | None = None
    thumbnail_path: str | None = None
    video_path: str | None = None
    youtube_url: str | None = None
    status: str = "created"     # created | imaged | rendered | uploaded
    created_at: datetime
    gates: dict = {}            # Gate 검증 이력

class Project(BaseModel):
    name: str
    songs: list[Song] = []
    output_dir: str
```

### 3.2 데이터 저장

각 프로젝트는 `output/{project_name}/` 디렉토리에 저장된다.
메타데이터는 `meta.json`에 기록한다.

```
output/
└── my_project/
    ├── meta.json               # Project 메타데이터
    ├── song_a1b2c3/
    │   ├── meta.json           # Song 메타데이터
    │   ├── audio.mp3
    │   ├── lyrics.txt
    │   ├── background.png
    │   ├── thumbnail.png
    │   └── video.mp4
    └── song_d4e5f6/
        └── ...
```

---

## 4. 외부 API 연동

### 4.1 YouTube Data API v3 (조회)

```
목적: 트렌드 음악 조회
엔드포인트: GET https://www.googleapis.com/youtube/v3/videos
파라미터: chart=mostPopular, regionCode=KR, videoCategoryId=10
인증: API Key
라이브러리: google-api-python-client
```

### 4.2 Suno API (곡 생성)

```
목적: AI 음악 생성
연동: suno-api 오픈소스 래퍼 (로컬 서버) 또는 서드파티 REST API
인증: Suno 유료 계정 쿠키 + 2Captcha API Key (hCaptcha 자동 해결)
의존: Node.js 18+, Playwright + 브라우저 (캡차 자동화용)
쿠키 갱신: ~7일마다 수동 갱신 필요
흐름: 프롬프트 전송 → (캡차 자동 해결) → 작업 ID 수신 → 폴링 → 완료 시 다운로드
```

### 4.3 Gemini Image API (이미지 생성)

```
목적: 배경 이미지 + 썸네일 생성
모델 (이미지): gemini-2.5-flash-image (기본)
              gemini-3.1-flash-image-preview (fallback)
모델 (텍스트): gemini-3-flash-preview (번역기 등)
              gemini-2.5-flash (fallback)
인증: Google AI API Key
라이브러리: google-genai
한도 처리: 429 RESOURCE_EXHAUSTED 시 친절 메시지 + 24h 대기 안내
```

### 4.4 YouTube Data API v3 (업로드)

```
목적: 영상 업로드
엔드포인트: POST https://www.googleapis.com/upload/youtube/v3/videos
인증: OAuth 2.0 (사용자 동의 필요)
라이브러리: google-api-python-client + google-auth-oauthlib
```

---

## 5. 설정 구조

```toml
# ~/.songmaker/config.toml

[youtube]
api_key = ""
client_id = ""
client_secret = ""
default_region = "KR"

[suno]
api_url = "http://localhost:3000"    # suno-api 로컬 서버
cookie = ""                          # ~7일마다 수동 갱신 필요
twocaptcha_key = ""                  # 2Captcha API Key (hCaptcha 해결용)
provider = "local"                   # "local" | "sunoapi.org"

[gemini]
api_key = ""
model = "gemini-2.5-flash-image"               # 이미지 메인
fallback_model = "gemini-3.1-flash-image-preview"  # 이미지 fallback
text_model = "gemini-3-flash-preview"          # 텍스트 (번역) 메인
text_fallback_model = "gemini-2.5-flash"       # 텍스트 fallback

[sheets]
service_account_path = "~/.songmaker/service_account.json"
default_sheet_id = ""                          # 시트 URL의 /d/<여기>/edit
worksheet = ""                                 # 빈 값이면 첫 번째 시트

[capcut]
inbox_dir = "~/CapCut/inbox"                   # mp3+썸네일 자동 복사 대상
outbox_dir = "~/CapCut/outbox"                 # CapCut export mp4 감지

[drive]
lyrics_parent_folder_id = ""                   # Drive 일별 백업 부모 폴더
archive_enabled = false

[output]
dir = ""                                       # 빈 값이면 cwd/output (cron은 절대경로 권장)

[render]
resolution = "1920x1080"
default_fade = 2
subtitle_font = ""                   # 빈 값이면 시스템 기본 폰트 (Windows: Malgun Gothic)

[upload]
default_privacy = "private"          # private | unlisted | public
```

---

## 6. 프로젝트(Project) 개념

`Project`는 한 번의 작업 세션에서 생성된 곡들의 묶음이다.

```
- 기본 프로젝트 이름: "project_{YYYYMMDD_HHMMSS}" (자동 생성)
- 사용자 지정: songmaker run --project "spring_ballads"
- 저장 위치: output/{project_name}/
- 프로젝트 내 곡: output/{project_name}/song_{uuid}/
```

`songmaker list`는 전체 프로젝트의 전체 곡을 표시한다.
`songmaker list --project spring_ballads`는 해당 프로젝트만 표시한다.

---

## 7. 로깅 전략

### 로그 레벨

| 레벨 | 사용처 | CLI 옵션 |
|------|--------|----------|
| ERROR | API 실패, 파일 손상, Gate 차단 실패 | 항상 출력 |
| WARNING | Gate 비차단 실패, fallback 전환 | 항상 출력 |
| INFO | Stage 시작/완료, Gate 통과, 진행 상황 | 기본 출력 |
| DEBUG | API 요청/응답 상세, FFmpeg 명령어, 프롬프트 전문 | `--verbose` 시 출력 |

### 로그 저장

```
~/.songmaker/logs/
└── songmaker_{YYYYMMDD}.log    # 일별 로그 파일
```

- CLI 출력: Rich 포맷 (컬러, 테이블)
- 파일 로그: 텍스트 포맷 (타임스탬프 + 레벨 + 메시지)
- API 키/토큰/쿠키: 로그에 절대 기록하지 않음 (마스킹)

---

## 8. 환경변수

config.toml 대신 환경변수로 설정 가능. 환경변수가 config.toml보다 우선한다.

| 환경변수 | config.toml 대응 | 설명 |
|---------|-----------------|------|
| `SONGMAKER_YOUTUBE_API_KEY` | `[youtube].api_key` | YouTube API Key |
| `SONGMAKER_YOUTUBE_CLIENT_ID` | `[youtube].client_id` | OAuth Client ID |
| `SONGMAKER_YOUTUBE_CLIENT_SECRET` | `[youtube].client_secret` | OAuth Client Secret |
| `SONGMAKER_YOUTUBE_REGION` | `[youtube].default_region` | 기본 지역 (KR) |
| `SONGMAKER_GEMINI_API_KEY` | `[gemini].api_key` | Gemini API Key |
| `SONGMAKER_GEMINI_MODEL` | `[gemini].model` | 이미지 모델 ID |
| `SONGMAKER_SUNO_API_URL` | `[suno].api_url` | Suno API 서버 URL |
| `SONGMAKER_SUNO_COOKIE` | `[suno].cookie` | Suno 인증 쿠키 (~7일마다 갱신) |
| `SONGMAKER_TWOCAPTCHA_KEY` | `[suno].twocaptcha_key` | 2Captcha API Key |
| `SONGMAKER_SUNO_PROVIDER` | `[suno].provider` | Suno 연동 방식 (local/sunoapi.org) |

---

## 9. 에러 처리 전략

| 상황 | 처리 |
|------|------|
| API 키 미설정 | `songmaker config` 안내 메시지 출력 후 종료 |
| API 호출 실패 | 3회 재시도 (지수 백오프), 실패 시 에러 메시지 + 중단 |
| Suno 생성 타임아웃 | 5분 대기 후 타임아웃, 재시도 안내 |
| FFmpeg 미설치 | 설치 안내 메시지 출력 후 종료 |
| 파이프라인 중간 실패 | 마지막 성공 Stage까지 저장, 해당 Stage부터 재실행 가능 |

---

## 10. 확장 포인트

현재 설계에서 추후 확장 가능한 지점:

| 확장 | 방법 |
|------|------|
| Suno → 다른 AI 음악 서비스 | `creator/` 내 새 모듈 추가, `cli.py`에서 선택 |
| Gemini → 다른 이미지 생성 | `imager/` 내 새 모듈 추가 |
| 트렌드 소스 추가 (멜론 등) | `trend/` 내 새 모듈 추가 |
| 업로드 대상 추가 (틱톡 등) | `uploader/` 내 새 모듈 추가 |
