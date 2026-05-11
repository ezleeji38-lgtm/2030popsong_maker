# Song Maker

> AI 작곡(Suno) + AI 이미지(Gemini) + Google Sheets 입력을 결합한 1인 운영 K-pop 플레이리스트 채널 자동화 CLI.

ChatGPT 챗봇이 만든 가사 → 구글 시트 → Suno 작곡 → Gemini 썸네일 → CapCut 영상 편집 → 수동 YouTube 업로드. 시트 한 줄에서 mp3+썸네일 한 쌍까지 한 번에 흐르도록 만들었다.

## 핵심 기능

| 기능 | 명령어 | 비고 |
|---|---|---|
| **챗봇 → 시트** 한 행 추가 | `songmaker append-row` | 가사 입력 양식 파싱·lint·중복 검사·시트 한 줄 추가 |
| **시트 → Suno** 일괄 처리 | `songmaker batch` | pending 행 → Suno 호출 → 다운로드 → 상태 갱신 |
| **단발 곡 생성 (시트 없이)** | `songmaker direct` | 캘리브레이션·테스트용. 시트 안 거치고 바로 Suno→이미지 |
| **5규칙 가사 변환** | `songmaker transform` | 원곡 가사 + 새 제목/내용 → Gemini가 5규칙(음절수·다른 단어·'/' 유지·발라드 감성·저작권 안전)으로 변환 |
| **시트 가사 일괄 변환** | `songmaker transform-batch` | 페르소나 시트의 G(원가사) 있고 J(새가사) 비어있는 행 자동 변환 |
| **페르소나 시트 일괄 곡 생성** | `songmaker batch-persona` | 페르소나 메이크 자동화 12컬럼 스키마 그대로 사용. Status=DO IT 행 처리 |
| **페르소나 시트 헤더 초기화** | `songmaker init-persona-sheet` | 빈 시트에 12컬럼 헤더 자동 작성 (1회 셋업) |
| **컨셉 시드 시트 푸시** | `songmaker seed-push` | `song_concepts_2030_monthly.md` 마크다운 표 → 시트 C/D/E열 일괄 입력 |
| **사전 점검** | `songmaker doctor` | 설치·키·서버·시트 접근 일괄 진단 |
| **사전 lint** | `songmaker lint` | pending 행 사전 검증 (빈 마커, 5000자 한도, 80자 제목 한도, 75% 유사 중복) |
| **챕터 타임라인** | `songmaker timeline` | 플레이리스트용 YouTube 챕터 텍스트 생성 |
| **다국어 번역** | `songmaker translate` | YouTube localizations용 50개 언어 번역 (Gemini) |
| **CapCut 핸드오프** | (auto on done) | mp3+썸네일을 CapCut 워치 폴더로 자동 복사 |
| **신용 잔량 점검** | `songmaker credits` | Suno 래퍼 GET /api/get_limit |

전체 23개 명령은 `songmaker --help` 참고.

## 두 가지 운영 모드

### Phase 0 — 캘리브레이션 (직접 호출)

가사·태그·제목을 CLI에 직접 넣어서 한 곡 생성. 운영 셋업 검증용.

```bash
songmaker direct \
  --title "Midnight Replay" \
  --tags "95 BPM, Modern Pop, Female vocal, nostalgic" \
  --lyrics-file lyrics.txt
```

### Phase 1 — 자동 생산 (시트 기반)

ChatGPT 챗봇이 가사 생성 → `append-row`로 시트 누적 → 10곡 모이면 `batch` 한 번 실행 → 모든 곡 자동 생성. 1인 운영자가 주 2-3회 발행하는 워크플로우를 자동화.

```bash
# 챗봇 출력을 시트에 한 행 추가
pbpaste | songmaker append-row -

# 10곡 모이면 일괄 생성
songmaker batch
```

### Phase 2 — 페르소나 메이크 자동화 시트 (원곡 참고 + 5규칙 변환)

기존 페르소나 메이크 자동화 시트 (12컬럼: Index/Status/Title1/Title2/Subject/Original Song/Original Lyric/Tag/Neg_tag/Song Lyric/Music URL/Persona ID)를 그대로 사용. 원곡 가사(G)를 참고해 새 가사(J)를 자동 변환한 뒤 Suno로 음악 생성.

```bash
# 1회 셋업: 빈 시트에 12컬럼 헤더 자동 작성
songmaker init-persona-sheet

# 컨셉 시드 15개를 시트 C/D/E열로 일괄 푸시
songmaker seed-push --count 15

# (수동) 각 행에 F(원곡)/G(원가사)/H(태그)/I(neg)/L(persona) 채우기

# 가사 5규칙 변환 — G + Title1 + Subject → J 채움 (Gemini)
songmaker transform-batch

# 시트 B열을 "DO IT"으로 설정한 행 → Suno로 음악 생성, K(Music URL) 채움
songmaker batch-persona
```

#### 5규칙 가사 변환 (`songmaker transform`)

원곡 1곡만 따로 변환하고 싶을 때:

```bash
songmaker transform \
  --title "Eaves Minute" \
  --subject "처마 밑에 잠시 같이 멈춘 일 분의 정적" \
  --lyrics-file original_song.txt
```

규칙:
1. 음절수와 띄어쓰기 그대로
2. 같은 단어 금지 (비슷한 발음의 다른 단어로 교체)
3. `/` 그대로 유지
4. 잔잔한 발라드 감성 + 현실적
5. 저작권 안전

## 아키텍처

```
ChatGPT 챗봇 (가사 생성)
   │
   ▼ TITLE/TAGS/LYRICS 양식 출력
songmaker append-row ──── sheet/parse.py (markdown·이모지 strip)
   │                  └─ validation/lint.py (5000자·80자·빈 마커 차단)
   │                  └─ validation/duplicate.py (75% 유사 차단)
   ▼
Google Sheet (Service Account 인증)
   │
   ▼ songmaker batch
creator/suno.py ── Suno API 래퍼 (Docker, localhost:3000)
   │              ├─ custom_generate (가사·태그 주입)
   │              ├─ 폴링 (POLL_INTERVAL=15s, TIMEOUT=10min)
   │              └─ 두 곡 중 duration 긴 곡 선택
   ▼
Gate 3 (오디오 검증: 파일·크기·디코딩·길이 60-360s)
   │
   ▼
imager/gemini.py ─ Gemini 2.5 Flash Image (Nano Banana)
   │              ├─ 배경 1920x1080
   │              └─ 썸네일 1280x720
   ▼
Gate 4 (이미지 검증: 파일·크기·디코딩·해상도)
   │
   ▼
capcut/ ── inbox 폴더로 mp3+썸네일 자동 복사 (사용자가 CapCut에서 편집)
   ▼
(수동) CapCut export → mp4 → 사용자가 직접 YouTube 업로드
```

각 Stage 사이에 **Gate**(검증 게이트)가 있다. 차단 실패 시 사용자에게 재시도/중단을 묻고, 비차단 경고는 기록만 하고 진행.

## 모듈 구조

```
src/song_maker/
├── cli.py                ─ 23개 명령 라우팅 (Typer)
├── config.py             ─ TOML + 환경변수 + chmod 600 저장
├── models.py             ─ Pydantic v2 데이터 모델
├── gates.py              ─ 검증 게이트 (Gate 1~6)
├── storage.py            ─ output_dir 동적 해결 (env > config > cwd)
│
├── trend/                ─ [Stage 1] YouTube 트렌드 (선택)
├── creator/              ─ [Stage 3] Suno 곡 생성
│   ├── suno.py           │   ├─ generate_song / generate_song_direct
│   │                     │   ├─ get_suno_credits
│   │                     │   └─ verify_gate3 (duration 분기: 60-360s 차단, 180-210s 권장)
│   └── prompt.py         │
├── imager/               ─ [Stage 4] Gemini 이미지
│   ├── gemini.py         │   ├─ generate_images
│   │                     │   ├─ 429 RESOURCE_EXHAUSTED 친절 메시지
│   │                     │   └─ verify_gate4 (파일·크기·디코딩·해상도)
│   └── prompt.py
├── renderer/             ─ [Stage 5] FFmpeg 영상 합성 (선택)
├── uploader/             ─ [Stage 6] YouTube OAuth (선택, 본 운영에선 비활성)
│
├── sheet/                ─ Google Sheets 통합
│   ├── client.py         │   ├─ 12컬럼 스키마 (status~updated_at)
│   │                     │   ├─ mark_done/processing/failed (batch_update, API 1회)
│   │                     │   └─ append_pending_row
│   └── parse.py          │   └─ TITLE/TAGS/LYRICS/PERSONA_ID 파싱
├── validation/           ─ 사전 검증
│   ├── lint.py           │   └─ 5000자·80자·빈 마커 차단
│   └── duplicate.py      │   └─ normalize + difflib SequenceMatcher 75% 임계
├── translator/           ─ Gemini 50개 언어 번역
├── playlist/             ─ 곡 묶음 → YouTube 챕터 타임라인
├── capcut/               ─ inbox/outbox 워치 폴더 핸드오프
└── drive/                ─ Drive 일별 가사 백업 (선택)
```

상세 설계는 `ARCHITECTURE.md` 참고.

## 요구사항

- Python 3.11+
- FFmpeg (영상 렌더링 시. 핵심 흐름엔 불필요)
- Docker Desktop (Suno 래퍼 컨테이너용)
- Suno Premier 또는 Pro 계정 (쿠키, ~7일마다 갱신)
- Google AI Studio Gemini API 키
- Google Cloud Service Account (시트·드라이브 접근)

## 설치

```bash
git clone https://github.com/ezleeji38-lgtm/2030popsong_maker.git
cd 2030popsong_maker
pip install -e .
```

## 설정

대화형:

```bash
songmaker config
```

`~/.songmaker/config.toml`에 chmod 600으로 저장. 환경변수가 config보다 우선.

| 키 | 발급처 |
|---|---|
| `gemini.api_key` | https://aistudio.google.com/apikey |
| `suno.api_url` | suno-api 로컬 Docker 서버 (기본 `http://localhost:3000`) |
| `sheets.service_account_path` | GCP Console → IAM → 서비스 계정 → 키 JSON |
| `sheets.default_sheet_id` | 시트 URL의 `/d/<여기>/edit` |

## 사전 점검

```bash
songmaker doctor
```

다음을 일괄 진단:

- Python · 패키지
- Gemini 키 + 모델 ListModels
- Suno 래퍼 응답 (`GET /api/get_limit`)
- Service Account JSON + 시트 접근
- FFmpeg (선택)
- output_dir 쓰기 권한

## 빠른 시작

### 1) 한 곡만 빠르게 (Phase 0)

```bash
# 가사 파일 준비
echo "[Verse 1]\nLate night, on read again" > lyrics.txt

# 한 곡 생성
songmaker direct \
  --title "Midnight Replay" \
  --tags "95 BPM, Modern Pop, Female vocal" \
  --lyrics-file lyrics.txt
```

결과: `output/{project}/{song_id}/audio.mp3`, `thumbnail.png`, `meta.json`

### 2) 시트 기반 (Phase 1)

```bash
# 1. ChatGPT 챗봇으로 가사 생성 → 출력 클립보드 복사
# 2. 시트에 한 행 추가
pbpaste | songmaker append-row -

# 3. 10곡 모이면 일괄 처리
songmaker batch
```

자세한 챗봇 지침 추가는 `docs/CHATBOT_SECTION_16.md` 참고.

## 외부 의존 서비스

| 서비스 | 용도 | 비용/제약 |
|---|---|---|
| **Suno** (Premier) | AI 작곡 | $30/월, 10,000 크레딧, 쿠키 7일 갱신 |
| **Gemini** (Free) | 이미지 + 텍스트 | 무료 (일 500장), 429 시 24h 대기 |
| **Google Sheets API** | 입력 시트 | 무료 (Service Account) |
| **2Captcha** (선택) | Suno hCaptcha 자동 해결 | $2.99 / 1000건 |
| **YouTube Data API** | 자동 업로드 | (본 운영에선 사용 안 함, 수동 업로드) |

## 운영 흐름 (1인 K-pop 채널)

```
[챗봇] 페르소나 메이크 자동화 워크플로우
  ├─ 컨셉 시드 (docs/song_concepts_2030_monthly.md, 60곡+)
  ├─ 원곡 참고 + Subject + 영문/한글 제목
  ├─ Claude/ChatGPT가 5규칙 가사 변환
  └─ TITLE/TAGS/LYRICS 양식 출력 (Section 16)
      │
      ▼
[songmaker append-row] → 시트 1행
      │
      ▼ (10곡 누적)
[songmaker batch] → Suno + Gemini 일괄
      │
      ▼
[CapCut inbox] mp3 + 썸네일 자동 복사
      │
      ▼ (수동)
[CapCut 편집] 자막·페이드·로고
      │
      ▼
[수동 YouTube 업로드]
```

## 디렉토리 구조

```
output/
└── {project_name}/                  # 기본 project_YYYYMMDD_HHMMSS
    ├── meta.json                    # 프로젝트 메타
    └── {song_id}/                   # UUID
        ├── meta.json                # Song + Gate 검증 이력
        ├── audio.mp3
        ├── lyrics.txt
        ├── input_lyrics.txt         # direct 모드 원본 (Suno 응답과 다를 수 있어 보존)
        ├── generated_lyrics.txt     # Advanced 모드 Suno 가사 생성 결과
        ├── background.png           # 1920x1080
        └── thumbnail.png            # 1280x720
```

## 문서

| 파일 | 내용 |
|---|---|
| `README.md` | 이 파일 |
| `ARCHITECTURE.md` | 시스템 아키텍처 상세 |
| `SOLO_SETUP.md` | 1인 운영자 셋업 가이드 (운영 단계별) |
| `docs/SETUP_GUIDE.md` | 외부 서비스 셋업 (Suno, Gemini, GCP) |
| `docs/CHATBOT_SECTION_16.md` | ChatGPT 챗봇에 추가할 출력 양식 |
| `docs/VERIFICATION.md` | Gate 검증 체크리스트 |
| `docs/RELIABILITY.md` | 재시도 전략 |
| `docs/SECURITY.md` | API 키 / 쿠키 보안 |
| `docs/song_concepts_2030_monthly.md` | 60곡 컨셉 시드 (지속 갱신) |

## 알려진 한계

- **Suno 쿠키 7일 만료**: 매주 수동 갱신 필요. doctor가 만료 시 친절 메시지.
- **Gemini 429 RESOURCE_EXHAUSTED**: 무료 일 한도 500장 초과 시 24h 대기.
- **시트 스키마 변경 시**: 헤더 12컬럼 정확히 맞춰야 함. `verify_schema()` 사전 점검.
- **YouTube 자동 업로드 비활성**: 본 운영은 CapCut 편집 후 수동 업로드 (영상 톤앤매너 일관성을 위해).

## 라이선스

MIT
