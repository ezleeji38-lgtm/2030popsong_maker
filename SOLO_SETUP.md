# Song Maker — 솔로 운영 셋업 가이드

본인 혼자 사용하는 자동화 파이프라인 셋업. 한 번 끝내면 평생 사용.

```
[ChatGPT 챗봇]  →  [songmaker append-row]  →  [Google Sheet]
                          ↓
                  [songmaker batch]
                          ↓
                  [Suno → Gemini → CapCut inbox]
                          ↓
                  [본인 CapCut 편집 → mp4 export]
                          ↓
                  [songmaker upload-capcut]
                          ↓
                  [YouTube 비공개 (50개국어 자동 번역)]
```

## 빠른 점검: songmaker doctor

셋업 완료 후 **반드시** 다음 명령으로 외부 의존성 한 번에 검증:
```bash
songmaker doctor
```
- ✓ FFmpeg/ffprobe / Suno 래퍼 / Gemini 키 / GCP SA / YouTube OAuth / 시트 접근
- ✗ 빨간 X 있으면 그 항목부터 수정. 다 ✓이면 운영 가능.

---

## 0. 필수 사전 조건

- macOS (현재 환경) 또는 Linux/Windows
- Python 3.11+ 설치
- FFmpeg 설치 (`brew install ffmpeg`)
- Docker (Suno 래퍼용 권장) 또는 Node.js 18+
- Suno 구독 (Pro/Premier — 본인 45,000원 Premier 있음)
- Google 계정 1개

---

## 1. 프로젝트 설치

```bash
cd /Users/ijiyeon/커서/songmaker-main
python3 -m pip install --user -e .
```

설치 확인:
```bash
songmaker --help
```

---

## 2. Suno 로컬 래퍼 띄우기 (핵심)

본인 Suno 구독 쿠키를 사용해서 `gcui-art/suno-api` 래퍼를 로컬에서 실행. 무료(추가비 0원).

### 2-1. Suno 쿠키 추출
1. 크롬에서 `https://suno.com` 로그인
2. F12 (개발자 도구) → Network 탭
3. 아무 페이지 새로고침 → 첫 요청 클릭
4. Headers → Request Headers → `Cookie:` 줄 전체 복사

### 2-2. Docker로 실행 (권장)
```bash
docker run -d \
  --name suno-api \
  -p 3000:3000 \
  -e SUNO_COOKIE="여기에_복사한_쿠키" \
  ghcr.io/gcui-art/suno-api:main
```

### 2-3. 동작 확인
```bash
curl http://localhost:3000/api/get_limit
# 응답에 credits 보이면 OK
```

> **주의**: 쿠키는 약 1주일마다 갱신 필요. 401/403 에러 나면 다시 추출.

---

## 3. Gemini API 키 (가사+이미지)

1. [Google AI Studio](https://aistudio.google.com/app/apikey) 접속
2. "Get API key" → "Create API key in new project"
3. 키 복사 (`AIza...`)
4. songmaker config에 등록:
   ```bash
   songmaker config
   # Gemini API Key 입력란에 붙여넣기
   ```

> **무료 티어**: 일 250 calls (Flash) / 100 images. 일 30곡까지 추가비 없음.

---

## 4. YouTube OAuth (업로드용)

### 4-1. Google Cloud Console 설정
1. [console.cloud.google.com](https://console.cloud.google.com) → 프로젝트 생성 (또는 기존)
2. "API 및 서비스" → "라이브러리" → **YouTube Data API v3** 사용 설정
3. "사용자 인증 정보" → "사용자 인증 정보 만들기" → **OAuth 클라이언트 ID**
4. 애플리케이션 유형: **데스크톱 앱**
5. JSON 다운로드 → `~/.songmaker/client_secret.json`로 저장:
   ```bash
   mkdir -p ~/.songmaker
   mv ~/Downloads/client_secret_*.json ~/.songmaker/client_secret.json
   ```

### 4-2. OAuth 동의 화면
1. "OAuth 동의 화면" → 사용자 유형 **외부**
2. 앱 이름/이메일만 채우고 저장
3. "테스트 사용자" 추가 → 본인 Gmail 등록
4. (publish 안 해도 본인은 사용 가능)

### 4-3. 첫 인증
첫 `songmaker upload` 실행 시 브라우저 열림 → 본인 계정 로그인 → 권한 승인 → 자동으로 `~/.songmaker/token.json` 저장됨.

> **YouTube API 한도**: 일 10,000 quota. 업로드 1건 = 1,600 quota → **일 6곡 가능**. 100곡은 17일 분산 필요. quota 늘리려면 Google에 신청 필요 (무료).

---

## 5. Google Sheets — Service Account 만들기

### 5-1. Sheets API + Drive API 활성화
1. Cloud Console → "라이브러리" → **Google Sheets API** 사용 설정
2. **Google Drive API**도 사용 설정

### 5-2. Service Account 생성
1. "사용자 인증 정보" → "사용자 인증 정보 만들기" → **서비스 계정**
2. 이름: `songmaker-sa` (아무거나)
3. 역할: 비워둠 (시트 권한만 따로 부여)
4. 만들기 후 → 해당 SA 클릭 → **키** 탭 → "키 추가" → JSON
5. 다운로드된 JSON을 저장:
   ```bash
   mv ~/Downloads/songmaker-*.json ~/.songmaker/service_account.json
   chmod 600 ~/.songmaker/service_account.json
   ```

### 5-3. Service Account 이메일 확인
다운로드 JSON 안의 `client_email` 필드 (예: `songmaker-sa@my-project-12345.iam.gserviceaccount.com`)

---

## 6. Google Sheet 만들기

### 6-1. 새 시트 생성
1. [sheets.new](https://sheets.new) 접속
2. **시트 1행에 헤더 입력** (정확히):
   ```
   status | title | lyrics | tags | persona_id | image_prompt | song_id | audio_url | youtube_url | error | updated_at
   ```
   (셀 11개 — A~K)

### 6-2. Service Account에 공유
1. 시트 우측 상단 "공유" 버튼
2. 위에서 확인한 SA 이메일 붙여넣기
3. 권한: **편집자**
4. "전송"

### 6-3. 시트 ID 추출
URL에서 `/d/` 뒤 `/edit` 앞 부분:
```
https://docs.google.com/spreadsheets/d/1abc...XYZ/edit
                                        ^^^^^^^^^^ 이게 시트 ID
```

### 6-4. config에 등록
`~/.songmaker/config.toml` 편집:
```toml
[sheets]
service_account_path = "~/.songmaker/service_account.json"
default_sheet_id = "1abc...XYZ"
worksheet = ""
```

---

## 7. ChatGPT 챗봇 → 시트 입력 흐름

### 7-1. 챗봇 system prompt에 Section 16 추가
본인 챗봇 지침서 마지막에 **`docs/CHATBOT_SECTION_16.md`** 내용을 그대로 추가.
이 섹션이 챗봇 출력을 `songmaker append-row`와 100% 호환되게 만듦.

### 7-2. 시트 입력 — `songmaker append-row` 추천 ⭐
챗봇이 출력한 마지막 양식 블록을 텍스트 파일로 저장 후:
```bash
# 파일에서
songmaker append-row chatbot_output.txt

# 또는 클립보드에서 직접
pbpaste | songmaker append-row -

# 또는 명시적으로
songmaker append-row \
  --title "Midnight Replay" \
  --tags "95 BPM, Modern Pop, Female vocal" \
  --lyrics-file lyrics.txt
```

자동으로:
- title/tags/lyrics 파싱 (마크다운/이모지/한국어 콜론 모두 OK)
- lint 검사 (빈 가사/너무 김/마커만 등 차단)
- 중복 검사 (75% 이상 차단, 이미 있는 가사 거부)
- 통과 시 시트에 status=pending 한 행 추가

### 7-3. 사전 점검 (선택)
시트 전체 점검:
```bash
songmaker lint     # 모든 pending 행 형식 + 중복 검사
songmaker credits  # Suno 잔여 크레딧 확인
```

---

## 8. 실행

### 8-0. Phase 0 — 캘리브레이션 (1곡 단발)
시트 셋업 없이 1곡 빠르게 만들어 품질 확인:
```bash
# 가사 lyrics.txt에 저장 후
songmaker direct \
  --title "Midnight Replay" \
  --lyrics-file lyrics.txt \
  --tags "95 BPM, Modern Pop, Female vocal, nostalgic"

# 곡만 만들고 이미지/업로드 스킵 (가장 빠른 테스트)
songmaker direct ... --skip-image --skip-upload
```
→ `~/CapCut/inbox/<song_id>/audio.mp3` 들어보고 만족하면 Phase 1으로.

### 8-1. Phase 1 — 시트 batch (10곡 단위)
```bash
songmaker batch --limit 10            # 10곡 처리
songmaker batch --limit 10 --skip-image  # 이미지 빼고 빠르게
songmaker batch --sheet <ID>          # 다른 시트 사용
```

### 8-2. 운영 명령
```bash
songmaker doctor          # 외부 의존성 사전점검
songmaker credits         # Suno 크레딧 잔여
songmaker lint            # 시트 사전 점검 (오류 미리 발견)
songmaker retry-failed    # status=failed 행을 pending으로 복구
songmaker timeline ~/CapCut/playlist/  # mp3 폴더 → 챕터 타임라인
songmaker upload-capcut --all  # outbox mp4 일괄 업로드

# 플레이리스트 (10곡 mix 영상 1개)
songmaker upload-capcut \
  --playlist ~/CapCut/outbox/mix.mp4 \
  --songs-dir ~/CapCut/playlist/ \
  --playlist-title "[playlist] 잠 안 올 때 듣는 K-Pop" \
  --translate \
  --thumbnail ~/CapCut/inbox/thumb.png
```

### 8-3. cron으로 자동화 (선택)
```bash
crontab -e
```
매일 오전 9시 실행:
```
0 9 * * * cd /Users/ijiyeon/커서/songmaker-main && /usr/local/bin/songmaker batch >> ~/.songmaker/batch.log 2>&1
```

---

## 9. 일일 페이스 가이드 (무료 운영 기준)

| 일일 곡수 | Gemini 텍스트 | Gemini 이미지 | YouTube | 결론 |
|---|---|---|---|---|
| 1~6곡 | 무료 OK | 무료 OK | OK | ✅ 완전 무료 |
| 7~30곡 | 무료 OK | 무료 OK (50/일 한도 안) | ⚠️ 6곡 초과시 분산 | ✅ 가능 |
| 31~50곡 | 무료 빠듯 | 무료 한도 초과 | ❌ 한도 초과 | ⚠️ Gemini 유료 또는 quota 신청 |
| 50곡↑ | 유료 권장 | 유료 권장 | quota 증액 필수 | 💸 비용 발생 |

**추천 페이스**: 하루 5~10곡, 한 달 150~300곡. 추가비 0원.

---

## 10. 트러블슈팅

| 증상 | 원인 | 해결 |
|---|---|---|
| `Suno 응답에 audio_url이 없습니다` | 쿠키 만료 | 2-1로 재추출, docker 재시작 |
| `시트 헤더 스키마 불일치` | 헤더 오타 | 6-1 헤더 정확히 입력 |
| `Service Account JSON 파일이 없습니다` | 경로 오류 | `~/.songmaker/service_account.json` 위치 확인 |
| `quotaExceeded` (Gemini) | 일일 한도 초과 | 다음날 또는 유료 |
| `quotaExceeded` (YouTube) | 1일 6곡 초과 | 분산 또는 quota 증액 신청 |
| 가사 생성 실패 (Suno) | 가사가 저작권 의심 | 챗봇 가사를 다시 생성 |
| 이미지 생성 실패 | Gemini 모델명 변경 | config의 `[gemini] model` 갱신 |

---

## 11. 일일 워크플로우 (정착 후)

### 매일 아침 (총 1.5~2시간)

1. **ChatGPT 챗봇** (5~10곡 × 10분 = 50~100분)
   - 챗봇과 대화하며 가사 완성
   - 마지막에 Section 16 양식 블록 출력
   - 텍스트 파일로 저장 (예: `daily/20260508_001.txt`)

2. **append-row** (5~10곡 × 5초 = 30~50초)
   ```bash
   for f in daily/20260508_*.txt; do
     songmaker append-row "$f"
   done
   ```
   각 파일이 lint+중복 검사 통과 시 시트에 행 추가됨

3. **사전 점검** (10초)
   ```bash
   songmaker lint     # 시트 형식 점검
   songmaker credits  # Suno 크레딧 확인
   ```

4. **batch 실행** (10곡 × 5~7분 = 50~70분, 백그라운드)
   ```bash
   songmaker batch
   ```
   → ~/CapCut/inbox/<song_id>/ 에 mp3 + 썸네일 + meta 자동 생성

5. **CapCut 편집** (10곡 × 2~3분 = 20~30분)
   - 템플릿 복제 → mp3 import → 제목 변경 → export
   - → ~/CapCut/outbox/<song_id>.mp4

6. **업로드** (10곡 일괄)
   ```bash
   songmaker upload-capcut --all --privacy private
   ```

### 표준 발행 사이클 (주 2-3회)

**1회 발행 = 15곡 신규 생성 → CapCut에서 15곡을 2번 이어붙임 → 약 90분 플레이리스트 영상**

```
[페르소나 시트에 15행 시드 입력]
  C(영문 제목) / D(한글 제목) / E(내용) / F(원곡) / G(원가사) / H(태그) / I(neg) / L(persona)
  ↓
[songmaker transform-batch]   ← 15행 G+C+E → J(새 가사) 자동 변환 (~3분, Gemini)
  ↓
[15행 모두 B열을 "DO IT"으로 변경]
  ↓
[songmaker batch-persona]     ← Suno + Gemini 일괄 (~45분 소요, 곡당 ~3분)
  → 15 mp3 + 15 thumbnail이 ~/CapCut/inbox/{project}/에 복사됨
  → 시트 K열에 Music URL 자동 기록
  ↓
[CapCut]
  - 15곡 시퀀스 만들기
  - 그 시퀀스를 한 번 더 복사해서 이어붙임 (= 15곡 × 2 루프)
  - 자막·페이드·로고 추가, 90분 mp4 export
  ↓
[songmaker timeline ~/CapCut/playlist/...]   ← 30챕터 텍스트 자동 생성
  → YouTube 설명란에 붙여넣기
  ↓
[수동 YouTube 업로드]
  - 비공개 → 검수 → 공개
```

**Suno 크레딧 예산** (Premier 10,000/월 기준):
- 1곡 ~500 크레딧 가정 → 월 20곡 가능
- 주 2회 × 15곡 = 월 120곡 필요 → **부족 가능성 높음**
- 실제 크레딧 측정: 첫 batch 후 `songmaker credits` 확인
- 부족하면 Pro 추가 구독 ($10/월) 또는 발행 빈도 조정

### 주간 1회 (10분)
- Suno 쿠키 갱신 (suno.com → F12 → Cookie 복사 → Docker 재시작)
- `songmaker doctor` 재실행해서 외부 의존성 OK 확인

### 매월 1회 (선택)
- 플레이리스트 영상 만들기:
  ```bash
  songmaker timeline ~/CapCut/playlist/2030_05/  # 타임라인 미리 확인
  songmaker upload-capcut \
    --playlist ~/CapCut/outbox/2030_05_mix.mp4 \
    --songs-dir ~/CapCut/playlist/2030_05/ \
    --playlist-title "[playlist] 2030 K-Pop Vol.5" \
    --translate
  ```

이상.
