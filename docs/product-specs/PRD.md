# Song Maker — Product Requirements Document (PRD)

## 1. 개요

**Song Maker**는 유튜브 트렌드 음악을 분석하고, AI로 곡을 생성하고, AI로 배경 이미지를 만들어 영상으로 렌더링한 뒤 유튜브에 업로드하는 CLI 기반 개인 자동화 도구이다.

- **플랫폼**: CLI (터미널)
- **언어**: Python 3.11+
- **사용자**: 개인 전용 (추후 GitHub을 통해 배포)

---

## 2. 핵심 워크플로우

```
[Stage 1]        [Stage 2]        [Stage 3]         [Stage 4]          [Stage 5]         [Stage 6]
트렌드 조사  →  사용자 선택  →  곡 생성(Suno)  →  이미지 생성  →  영상 렌더링  →  유튜브 업로드
                                                   (Gemini)         (FFmpeg)
```

---

## 3. Stage 상세

### 3.1 Stage 1 — 트렌드 조사

YouTube Data API v3를 사용하여 현재 인기 음악을 조사하고 사용자에게 보고한다.

| 항목 | 설명 |
|------|------|
| **데이터 소스** | YouTube Data API v3 (`videos.list`, `chart=mostPopular`) |
| **조회 범위** | 한국(KR) 기본, `--region` 옵션으로 변경 가능 |
| **카테고리** | Music (categoryId: 10) |
| **수집 정보** | 제목, 아티스트(채널명), 조회수, 태그, 게시일 |
| **출력** | CLI 테이블 + 트렌드 요약 |

**출력 예시:**
```
 현재 유튜브 인기 음악 (한국)

 #  제목                    아티스트       조회수      태그
 1  Spring Breeze           IU            12.3M      발라드, 봄
 2  Next Level              aespa          8.7M      댄스, K-pop
 3  Love Dive               IVE            6.2M      팝, K-pop

 트렌드 분석:
 - 주요 장르: 발라드 (40%), K-pop 댄스 (35%), 인디 (25%)
 - 키워드: 봄, 사랑, 이별
```

### 3.2 Stage 2 — 사용자 선택

트렌드 보고를 기반으로 사용자가 곡의 방향을 결정한다.

| 입력 항목 | 필수 | 설명 |
|-----------|------|------|
| **장르** | O | 발라드, K-pop, 힙합, 인디 등 |
| **분위기** | O | 밝은, 슬픈, 에너지틱, 몽환적 등 |
| **주제** | O | 곡의 주제 (예: "봄날의 설렘") |
| **가사 키워드** | X | 포함하고 싶은 단어/문장 |
| **참고곡** | X | 트렌드 목록 번호 또는 직접 입력 |
| **곡 수** | O | 한 번에 생성할 곡 수 (기본: 1) |

### 3.3 Stage 3 — 곡 생성 (Suno)

사용자 입력을 바탕으로 Suno AI를 통해 곡을 생성한다.

| 항목 | 설명 |
|------|------|
| **생성 엔진** | Suno AI |
| **연동 방식** | 1순위: [suno-api](https://github.com/gcui-art/suno-api) 오픈소스 래퍼 |
|               | 2순위: [sunoapi.org](https://sunoapi.org/) 서드파티 API |
| **입력** | 장르, 분위기, 주제, 가사 키워드 → 프롬프트 변환 |
| **출력** | MP3/WAV 오디오 파일 + 가사 텍스트 |
| **저장** | `output/{project_name}/{song_id}/audio.mp3` |

**흐름:**
```
사용자 입력 → 프롬프트 조합 → Suno API 호출 → 생성 대기 → 오디오 다운로드 → 로컬 저장
```

> **참고**: Suno 공식 API는 없음. 서드파티 래퍼에 의존하며, 공식 API 출시 시 전환한다.

### 3.4 Stage 4 — 이미지 생성 (Gemini)

곡의 분위기에 맞는 배경 이미지를 Gemini AI로 자동 생성한다.

| 항목 | 설명 |
|------|------|
| **API** | Google Gen AI SDK (`google-genai`) |
| **모델** | `gemini-3.1-flash-image-preview` (Nano Banana 2, 최신) |
| **대체 모델** | `gemini-3-pro-image-preview` (고품질 필요 시) |
| **해상도** | 1920x1080 (유튜브 영상용) |
| **무료 할당량** | 하루 500장 (Google AI Studio 무료 티어) |
| **인증** | Google AI API Key |

**이미지 생성 전략:**
| 생성 항목 | 설명 |
|-----------|------|
| **배경 이미지** | 곡의 분위기/주제를 반영한 아트워크 (1장 이상) |
| **썸네일** | 유튜브 썸네일용 이미지 (제목 텍스트 포함) |
| **프롬프트** | 장르 + 분위기 + 주제 → 이미지 프롬프트 자동 생성 |

**흐름:**
```
곡 메타데이터(장르/분위기/주제) → 이미지 프롬프트 생성 → Gemini API 호출 → 이미지 다운로드 → 로컬 저장
```

**프롬프트 예시:**
```
곡 정보: 장르=발라드, 분위기=몽환적, 주제=봄날의 설렘
→ 이미지 프롬프트: "A dreamy spring landscape with cherry blossoms floating
   in warm golden light, soft pastel colors, cinematic wide shot, 16:9 aspect ratio"
```

**저장:**
```
output/{project_name}/{song_id}/
├── audio.mp3
├── lyrics.txt
├── background.png      ← 배경 이미지
└── thumbnail.png       ← 썸네일
```

### 3.5 Stage 5 — 영상 렌더링 (FFmpeg)

생성된 오디오 + 이미지를 합쳐 유튜브용 MP4 영상으로 렌더링한다.

| 항목 | 설명 |
|------|------|
| **도구** | FFmpeg (로컬 설치 필수) |
| **입력** | 오디오(MP3) + 배경 이미지(PNG) + 가사(SRT, 선택) |
| **출력** | MP4 (H.264 + AAC) |
| **해상도** | 1920x1080 (기본) |

**렌더링 옵션:**
| 옵션 | 설명 |
|------|------|
| `--subtitles` | 가사 자막 포함 여부 |
| `--fade` | 페이드인/아웃 효과 (초 단위) |
| `--resolution` | 출력 해상도 변경 |

**출력:**
```
output/{project_name}/{song_id}/
├── audio.mp3
├── lyrics.txt
├── background.png
├── thumbnail.png
└── video.mp4           ← 최종 영상
```

### 3.6 Stage 6 — 유튜브 업로드

렌더링된 영상을 YouTube Data API v3로 업로드한다.

| 항목 | 설명 |
|------|------|
| **API** | YouTube Data API v3 (`videos.insert`) |
| **인증** | OAuth 2.0 (최초 1회 브라우저 인증) |
| **자동 생성** | 제목, 설명, 태그 (곡 메타데이터 기반) |
| **썸네일** | Stage 4에서 생성한 thumbnail.png 자동 설정 |
| **공개 설정** | 비공개(기본) → 사용자 확인 후 공개 전환 |

---

## 4. CLI 명령어 구조

```bash
# 전체 파이프라인
songmaker run                         # Stage 1~6 순차 실행

# 개별 단계
songmaker trend                       # Stage 1: 트렌드 조사
songmaker create                      # Stage 2~3: 사용자 입력 + 곡 생성
songmaker image <song_id>             # Stage 4: 이미지 생성
songmaker render <song_id>            # Stage 5: 영상 렌더링
songmaker upload <song_id>            # Stage 6: 유튜브 업로드

# 수동 임포트 (Suno API 실패 시 대안)
songmaker import <mp3_path>           # MP3 파일 직접 등록, Stage 4부터 재개

# 관리
songmaker config                      # API 키 설정
songmaker list                        # 생성된 곡 목록
songmaker status <song_id>            # 곡 상태 확인
```

---

## 5. 기술 스택

| 구분 | 기술 |
|------|------|
| **언어** | Python 3.11+ |
| **CLI** | Typer |
| **YouTube API** | google-api-python-client |
| **Suno 연동** | suno-api 오픈소스 래퍼 또는 서드파티 REST API |
| **이미지 생성** | google-genai (Gemini API) |
| **영상 렌더링** | FFmpeg (subprocess) |
| **데이터 저장** | JSON 파일 |
| **설정 관리** | TOML (`~/.songmaker/config.toml`) |
| **배포** | GitHub + `pip install` (pyproject.toml) |

---

## 6. 프로젝트 디렉토리 구조

```
song_maker/
├── src/
│   └── song_maker/
│       ├── __init__.py
│       ├── cli.py                # CLI 진입점 (Typer)
│       ├── config.py             # 설정 관리
│       ├── models.py             # 데이터 모델 (Pydantic)
│       ├── gates.py              # 검증 게이트 (Gate 1~6)
│       ├── trend/                # Stage 1: 트렌드 조사
│       │   ├── __init__.py
│       │   ├── youtube.py        # YouTube API 연동
│       │   └── analyzer.py       # 트렌드 분석/요약
│       ├── creator/              # Stage 2~3: 곡 생성
│       │   ├── __init__.py
│       │   ├── suno.py           # Suno API 연동
│       │   └── prompt.py         # 프롬프트 생성
│       ├── imager/               # Stage 4: 이미지 생성
│       │   ├── __init__.py
│       │   ├── gemini.py         # Gemini API 연동
│       │   └── prompt.py         # 이미지 프롬프트 생성
│       ├── renderer/             # Stage 5: 영상 렌더링
│       │   ├── __init__.py
│       │   └── ffmpeg.py         # FFmpeg 렌더링
│       └── uploader/             # Stage 6: 유튜브 업로드
│           ├── __init__.py
│           └── youtube.py        # YouTube 업로드
├── output/                       # 생성물 저장
├── tests/
├── pyproject.toml
└── README.md
```

---

## 7. 외부 의존성 및 API 키

| 서비스 | 필요한 인증 | 비용 |
|--------|------------|------|
| **YouTube Data API v3** | Google Cloud API Key + OAuth 2.0 | 무료 (일일 10,000 유닛) |
| **Gemini Image API** | Google AI API Key | 무료 (일일 500장) |
| **Suno AI** | Suno 유료 계정 (쿠키 기반) + 2Captcha API Key | Suno Pro/Premier + 2Captcha (~$2.99/1,000건) |
| **FFmpeg** | 로컬 설치 | 무료 |

---

## 8. 개발 우선순위

| 순서 | 기능 | 단계 | 우선도 |
|------|------|------|--------|
| 1 | CLI 뼈대 + 설정 관리 | - | P0 |
| 2 | YouTube 트렌드 조사 | Stage 1 | P0 |
| 3 | 사용자 입력 인터페이스 | Stage 2 | P0 |
| 4 | Suno 곡 생성 연동 | Stage 3 | P0 |
| 5 | Gemini 이미지 생성 | Stage 4 | P0 |
| 6 | FFmpeg 영상 렌더링 | Stage 5 | P1 |
| 7 | YouTube 업로드 | Stage 6 | P1 |
| 8 | 배치 처리 (여러 곡) | 전체 | P2 |

---

## 9. 제약 사항 및 리스크

| 리스크 | 설명 | 대응 |
|--------|------|------|
| **Suno API 불안정** | 500 에러 빈발, 쿠키 ~7일마다 만료 | 대안 3종: 수동 MP3 임포트(`songmaker import`), 서드파티 API 전환, 다른 AI 음악 서비스 |
| **Suno 캡차 (hCaptcha)** | 유료 계정도 캡차 필수. 2Captcha 유료 서비스 필요 | 2Captcha 자동 해결 + 잔액 모니터링. Windows에서 빈도 높음 |
| **Suno 공식 API 부재** | 서드파티 래퍼 의존 | 어댑터 패턴으로 교체 용이하게 설계 |
| **Gemini 프리뷰 모델** | 모델 ID/API 변경 가능 | config.toml에서 모델 관리, fallback 모델 설정 |
| **YouTube API 할당량** | 일일 10,000 유닛 | 업로드 횟수 제한(~5곡/일), 캐싱 |
| **Suno ToS** | API 래퍼 사용 ToS 위반 가능 | 공식 API 출시 시 전환 |
| **AI 이미지 품질** | 프롬프트에 따라 품질 편차 | 프롬프트 템플릿 최적화, 재생성 옵션 |
| **저작권** | AI 생성물 저작권 이슈 | 업로드 전 사용자 확인 단계 |
