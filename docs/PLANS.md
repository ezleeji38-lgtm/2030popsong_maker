# Song Maker — Development Plan

## 1. 개발 페이즈

전체 개발을 4개 페이즈로 나눈다. 각 페이즈는 독립적으로 동작 가능한 단위이다.

---

## Phase 1 — 기반 구축 + 트렌드 조사

**목표**: CLI 뼈대 완성, YouTube 트렌드 조회 동작

| 작업 | 산출물 |
|------|--------|
| pyproject.toml 설정, 패키지 구조 생성 | 프로젝트 스캐폴딩 |
| config.py: TOML 설정 로드/저장 | `~/.songmaker/config.toml` |
| models.py: 핵심 데이터 모델 정의 | TrendItem, TrendReport, SongRequest, Song |
| cli.py: Typer 앱 기본 명령어 | `songmaker trend`, `songmaker config` |
| trend/youtube.py: YouTube API 연동 | 트렌드 음악 조회 |
| trend/analyzer.py: 트렌드 분석 | 장르/키워드 집계, 테이블 출력 |

**완료 기준**: `songmaker trend` 실행 시 한국 인기 음악 목록 출력

---

## Phase 2 — 곡 생성 + 이미지 생성

**목표**: 사용자 입력 → Suno 곡 생성 → Gemini 이미지 생성

| 작업 | 산출물 |
|------|--------|
| CLI 대화형 입력 (Stage 2) | `songmaker create` 명령어 |
| creator/prompt.py: 프롬프트 생성 | 사용자 입력 → Suno 프롬프트 |
| creator/suno.py: Suno API 연동 | 곡 생성, 폴링, 다운로드 |
| imager/prompt.py: 이미지 프롬프트 생성 | 곡 메타 → 이미지 프롬프트 |
| imager/gemini.py: Gemini API 연동 | 배경 + 썸네일 생성 |
| output/ 저장 구조 | meta.json + 파일 저장 |

**완료 기준**: `songmaker create` → 오디오 + 이미지 파일이 output/에 저장됨

---

## Phase 3 — 렌더링 + 업로드

**목표**: 영상 렌더링 후 YouTube 업로드까지 완료

| 작업 | 산출물 |
|------|--------|
| renderer/ffmpeg.py: FFmpeg 렌더링 | `songmaker render <song_id>` |
| 가사 자막 SRT 생성 | lyrics.txt → subtitles.srt 변환 |
| uploader/youtube.py: OAuth 인증 | 토큰 저장/갱신 |
| uploader/youtube.py: 영상 업로드 | `songmaker upload <song_id>` |
| 메타데이터 자동 생성 | 제목, 설명, 태그, 썸네일 |

**완료 기준**: `songmaker render` + `songmaker upload` → YouTube에 비공개 영상 업로드됨

---

## Phase 4 — 통합 + 배포

**목표**: 전체 파이프라인 통합, GitHub 배포 준비

| 작업 | 산출물 |
|------|--------|
| `songmaker run`: 전체 파이프라인 | Stage 1~6 순차 실행 |
| `songmaker list`, `songmaker status` | 곡 관리 명령어 |
| 배치 처리: 여러 곡 한번에 | count > 1 지원 |
| README.md 작성 | 설치/사용 가이드 |
| pyproject.toml 완성 | `pip install` 가능 |
| GitHub 저장소 세팅 | .gitignore, LICENSE |

**완료 기준**: `pip install .` 후 `songmaker run`으로 전체 워크플로우 실행 가능

---

## 2. 페이즈별 의존성

```
Phase 1 (기반 + 트렌드)
   │
   ▼
Phase 2 (곡 생성 + 이미지)
   │
   ▼
Phase 3 (렌더링 + 업로드)
   │
   ▼
Phase 4 (통합 + 배포)
```

Phase 1이 완료되어야 Phase 2 진행 가능.
Phase 2 내에서 곡 생성과 이미지 생성은 병렬 개발 가능.
