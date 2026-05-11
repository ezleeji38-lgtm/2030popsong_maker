# Song Maker — Technical Design

## 1. 설계 원칙

| 원칙 | 설명 |
|------|------|
| **Stage 독립성** | 각 Stage는 독립 모듈. 다른 Stage를 직접 import하지 않는다. |
| **파일 기반 상태** | Stage 간 데이터 전달은 파일시스템(output/) + JSON 메타데이터로 한다. |
| **CLI 오케스트레이션** | `cli.py`가 유일한 오케스트레이터. Stage 실행 순서와 데이터 전달을 관리한다. |
| **어댑터 패턴** | 외부 API(Suno, Gemini)는 어댑터로 감싸서 교체 용이하게 한다. |
| **설정 분리** | API 키, 모델명 등은 코드에 하드코딩하지 않고 config.toml에서 관리한다. |

---

## 2. Stage별 기술 설계

### 2.1 Stage 1 — 트렌드 조사 (`trend/`)

**youtube.py**
```
fetch_trending(region: str, max_results: int) -> list[TrendItem]
```
- `google-api-python-client`의 `youtube.videos().list()` 호출
- `chart=mostPopular`, `videoCategoryId=10` (Music)
- `regionCode` 파라미터로 지역 설정
- snippet(제목, 채널, 태그) + statistics(조회수) 파트 요청

**analyzer.py**
```
analyze(items: list[TrendItem]) -> TrendReport
```
- 태그에서 장르 키워드 추출 (미리 정의된 장르 매핑 테이블)
- 빈도 기반 상위 장르/키워드 집계
- CLI 출력용 테이블 포맷팅 (`rich` 라이브러리 활용)

### 2.2 Stage 2 — 사용자 입력 (CLI)

- `typer.prompt()`로 대화형 입력 수집
- 트렌드 목록 표시 후 참고곡 선택 가능
- 입력 결과를 `SongRequest` 모델로 변환
- 입력 검증: 필수 필드 누락 시 재입력 요청

### 2.3 Stage 3 — 곡 생성 (`creator/`)

**prompt.py**
```
build_suno_prompt(request: SongRequest) -> dict
```
- `SongRequest` → Suno API가 이해하는 프롬프트 형태로 변환
- 장르/분위기/주제를 영문 태그로 매핑
- 가사 키워드 포함 시 커스텀 가사 모드

**suno.py**
```
generate(prompt: dict) -> Song
download(song_id: str, output_dir: Path) -> Path
poll_status(task_id: str) -> str
```
- suno-api 래퍼 서버에 HTTP 요청
- 비동기 생성: task_id 수신 → 폴링(5초 간격) → 완료 시 다운로드
- 다운로드한 MP3와 가사를 `output/`에 저장
- 실패 시 3회 재시도

### 2.4 Stage 4 — 이미지 생성 (`imager/`)

**prompt.py**
```
build_image_prompt(song: Song) -> str
build_thumbnail_prompt(song: Song) -> str
```
- 곡의 장르/분위기/주제를 영문 이미지 프롬프트로 변환
- 배경: 풍경/추상 아트 스타일, 16:9, 텍스트 없음
- 썸네일: 곡 제목 텍스트 포함, 눈에 띄는 구도

**gemini.py**
```
generate_image(prompt: str, output_path: Path) -> Path
```
- `google-genai` SDK 사용
- 모델: config에서 설정 (`gemini-3.1-flash-image-preview` 기본)
- 응답에서 이미지 바이트 추출 → PNG 저장
- 실패 시 fallback 모델로 재시도

### 2.5 Stage 5 — 영상 렌더링 (`renderer/`)

**ffmpeg.py**
```
render(audio: Path, background: Path, output: Path, options: RenderOptions) -> Path
```
- FFmpeg를 subprocess로 호출
- 기본 명령어 구조:
  ```
  ffmpeg -loop 1 -i background.png -i audio.mp3
         -c:v libx264 -tune stillimage -c:a aac
         -b:a 192k -pix_fmt yuv420p
         -shortest output.mp4
  ```
- 옵션: 가사 자막(`-vf subtitles`), 페이드(`-vf fade`), 해상도(`-s`)
- FFmpeg 미설치 감지: `shutil.which("ffmpeg")` 체크

### 2.6 Stage 6 — 유튜브 업로드 (`uploader/`)

**youtube.py**
```
authenticate() -> Credentials
upload(video: Path, metadata: dict, thumbnail: Path | None) -> str
```
- OAuth 2.0 인증: 최초 실행 시 브라우저 열림 → 토큰 저장 (`~/.songmaker/token.json`)
- 이후 실행 시 저장된 토큰 자동 사용 (만료 시 자동 갱신)
- 업로드 시 메타데이터 자동 생성:
  - 제목: `{주제} | {장르}` 형태
  - 설명: 가사 + 생성 정보
  - 태그: 장르, 분위기, 키워드
- 기본 비공개 업로드 → 사용자 확인 후 공개 전환

---

## 3. 파이프라인 실행 흐름

```
songmaker run
│
├─ [Stage 1] trend/youtube.py  → fetch_trending("KR")
│            trend/analyzer.py → analyze(items) → TrendReport
│            → CLI 테이블 출력
├─ [Gate 1]  gates.py → verify_gate1(report)
│            → API 응답 + 결과 수 + 데이터 유효성 검증
│
├─ [Stage 2] CLI 대화형 입력 수집
│            → SongRequest 생성
├─ [Gate 2]  gates.py → verify_gate2(request)
│            → 필수 입력 완료 + 곡 수 범위 + 참고곡 번호 검증
│
├─ [Stage 3] creator/prompt.py → build_suno_prompt(request)
│            creator/suno.py  → generate(prompt) → 폴링 → download()
│            → audio.mp3, lyrics.txt 저장
├─ [Gate 3]  gates.py → verify_gate3(song)
│            → 파일 존재 + 크기 + 오디오 무결성 검증
│
├─ [Stage 4] imager/prompt.py  → build_image_prompt(song)
│            imager/gemini.py → generate_image(prompt)
│            → background.png, thumbnail.png 저장
├─ [Gate 4]  gates.py → verify_gate4(song)
│            → 이미지 존재 + 디코딩 + 해상도 검증
│
├─ [Stage 5] renderer/ffmpeg.py → render(audio, background)
│            → video.mp4 저장
├─ [Gate 5]  gates.py → verify_gate5(song)
│            → FFmpeg 종료코드 + 스트림 + 크기 + 길이 검증
│
├─ [Stage 6] uploader/youtube.py → authenticate() → upload(video, metadata)
│            → YouTube URL 반환
├─ [Gate 6]  gates.py → verify_gate6(song)
│            → 업로드 응답 + URL + 메타데이터 검증
│
└─ 완료: 곡 상태를 "uploaded"로 업데이트, URL 출력
```

각 Gate에서 차단(blocking) 검증 실패 시 재시도/건너뛰기/중단으로 분기한다.
비차단(non-blocking) 검증 실패 시 경고 출력 후 다음 Stage로 진행한다.
Gate 검증 결과는 `meta.json`의 `gates` 필드에 기록된다.

---

## 4. 동기/비동기 아키텍처 결정

**결정: 동기(sync) 방식 사용. async를 쓰지 않는다.**

| 근거 | 설명 |
|------|------|
| Typer 호환성 | Typer는 async를 네이티브 지원하지 않음. `async-typer` 래퍼 존재하나 유지보수 불확실 |
| 파이프라인 특성 | Stage가 순차 실행됨. 동시성이 필요한 구간 없음 |
| 외부 SDK | Gemini SDK(`google-genai`)는 동기 호출. YouTube SDK도 동기 |
| Suno 폴링 | `httpx` 동기 클라이언트 + `time.sleep()` 루프로 충분 |

**적용:**
- `creator/suno.py`: `httpx.Client` (동기) 사용. 폴링은 `time.sleep(5)` 루프
- `imager/gemini.py`: `client.models.generate_content()` (동기) 사용
- `uploader/youtube.py`: `google-api-python-client` (동기) 사용
- CLI: `typer.run()` 표준 사용. `asyncio` 불필요

---

## 5. 의존 라이브러리

```toml
[project]
dependencies = [
    "typer>=0.9",
    "rich>=13.0",
    "google-api-python-client>=2.0",
    "google-auth-oauthlib>=1.0",
    "google-genai>=1.0",
    "httpx>=0.27",
    "pydantic>=2.0",
    "tomli-w>=1.0",
]
```

| 라이브러리 | 용도 |
|-----------|------|
| `typer` | CLI 프레임워크 |
| `rich` | 터미널 테이블/진행바 출력 |
| `google-api-python-client` | YouTube Data API |
| `google-auth-oauthlib` | YouTube OAuth 인증 |
| `google-genai` | Gemini Image API |
| `httpx` | Suno API HTTP 호출 |
| `pydantic` | 데이터 모델 검증 |
| `tomli-w` | TOML 쓰기 (`tomllib`는 읽기 전용) |
