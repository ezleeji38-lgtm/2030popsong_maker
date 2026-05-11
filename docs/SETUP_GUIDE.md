# Song Maker — Setup Guide (사전 준비 가이드)

Song Maker를 사용하기 위해 필요한 외부 서비스 설정 및 도구 설치 안내.

---

## 1. Python 설치

```bash
# Python 3.11 이상 필요
python --version    # 3.11+ 확인
```

- Windows: https://www.python.org/downloads/
- macOS: `brew install python@3.11`
- Linux: `sudo apt install python3.11`

---

## 2. FFmpeg 설치

영상 렌더링(Stage 5)에 필요.

### Windows
```
1. https://ffmpeg.org/download.html 에서 다운로드
2. 압축 해제 후 bin/ 폴더를 시스템 PATH에 추가
3. 확인: ffmpeg -version
```

### macOS
```bash
brew install ffmpeg
```

### Linux
```bash
sudo apt install ffmpeg
```

### 설치 확인
```bash
ffmpeg -version
ffprobe -version
```

---

## 3. YouTube Data API v3 설정

트렌드 조회(Stage 1)와 업로드(Stage 6)에 필요.

### 3.1 API Key 발급 (트렌드 조회용)

```
1. https://console.cloud.google.com/ 접속
2. 새 프로젝트 생성 (예: "Song Maker")
3. "API 및 서비스" → "라이브러리" → "YouTube Data API v3" 검색 → 사용 설정
4. "API 및 서비스" → "사용자 인증 정보" → "사용자 인증 정보 만들기" → "API 키"
5. 생성된 API 키 복사
```

### 3.2 OAuth 2.0 클라이언트 (업로드용)

```
1. Google Cloud Console → "API 및 서비스" → "사용자 인증 정보"
2. "사용자 인증 정보 만들기" → "OAuth 클라이언트 ID"
3. 앱 유형: "데스크톱 앱"
4. 이름: "Song Maker"
5. 생성 후 "JSON 다운로드" → client_secret.json 저장
6. 파일을 ~/.songmaker/client_secret.json 에 복사
```

### 3.3 OAuth 동의 화면 설정

```
1. Google Cloud Console → "API 및 서비스" → "OAuth 동의 화면"
2. 사용자 유형: "외부" 선택
3. 앱 이름: "Song Maker"
4. 범위 추가:
   - https://www.googleapis.com/auth/youtube.upload
   - https://www.googleapis.com/auth/youtube
5. 테스트 사용자에 본인 Gmail 추가
```

> **주의**: OAuth 동의 화면이 "테스트" 상태이면 테스트 사용자만 인증 가능.
> 개인 사용이면 테스트 상태로 충분.

---

## 4. Gemini API Key 발급

이미지 생성(Stage 4)에 필요.

```
1. https://aistudio.google.com/ 접속 (Google 계정 로그인)
2. 좌측 메뉴 → "Get API Key" → "Create API Key"
3. 프로젝트 선택 또는 새 프로젝트 생성
4. 생성된 API 키 복사
```

**무료 할당량**: 하루 500장 (개인 사용 충분)

---

## 5. Suno 계정 설정

곡 생성(Stage 3)에 필요. **유료 계정 + 2Captcha + suno-api** 3가지 모두 필요.

### 5.1 Suno 유료 계정

```
1. https://suno.com/ 접속
2. 계정 생성 (Google/Discord/Microsoft)
3. Pro 또는 Premier 구독 (상업적 사용권 + 크레딧)
   - Pro: $10/월, 2,500 크레딧/월
   - Premier: $30/월, 10,000 크레딧/월
```

> **주의**: 유료 계정이어도 hCaptcha는 면제되지 않는다.

### 5.2 2Captcha 설정 (hCaptcha 자동 해결)

```
1. https://2captcha.com/ 에서 계정 생성
2. 잔액 충전 (최소 $1, hCaptcha 1,000건당 ~$2.99)
3. Dashboard → API Key 복사
```

> **주의**: 2Captcha 잔액이 0이면 곡 생성이 불가능하다.
> Windows 환경에서는 캡차 빈도가 높아 잔액 소모가 빠를 수 있다.

### 5.3 suno-api 래퍼 설치

```bash
# Node.js 18+ 필요
node --version

# suno-api 클론 및 설치
git clone https://github.com/gcui-art/suno-api.git
cd suno-api
npm install

# Playwright 브라우저 설치 (캡차 자동화에 필요)
npx playwright install chromium
```

### 5.4 suno-api 환경변수 설정

```bash
# suno-api/.env 파일 생성
cat > .env << 'EOF'
SUNO_COOKIE=your_cookie_here
TWOCAPTCHA_KEY=your_2captcha_api_key
BROWSER=chromium
BROWSER_HEADLESS=true
EOF
```

### 5.5 쿠키 획득 방법 (~7일마다 반복)

```
1. 브라우저에서 https://suno.com/ 로그인
2. 개발자 도구 열기 (F12)
3. Network 탭 → 페이지 새로고침
4. "?__clerk_api_version" 포함된 요청 찾기 → 클릭
5. Headers 탭 → Cookie 값 전체 복사
6. suno-api/.env의 SUNO_COOKIE에 붙여넣기
7. suno-api 서버 재시작
```

> **중요**: 쿠키는 약 **7일마다 만료**된다. 만료 시 위 과정을 반복해야 한다.

### 5.6 suno-api 서버 실행

```bash
cd suno-api
npm run dev
# 기본 포트: http://localhost:3000

# 정상 동작 확인
curl http://localhost:3000/api/get_limit
```

---

## 6. Song Maker 설정

### 6.1 설치

```bash
git clone https://github.com/your-username/song-maker.git
cd song-maker
pip install -e .
```

### 6.2 API 키 설정

```bash
songmaker config
```

대화형으로 입력:
```
? YouTube API Key: AIza...
? Gemini API Key: AIza...
? Suno API URL [http://localhost:3000]:
```

또는 환경변수:
```bash
export SONGMAKER_YOUTUBE_API_KEY="AIza..."
export SONGMAKER_GEMINI_API_KEY="AIza..."
export SONGMAKER_SUNO_API_URL="http://localhost:3000"
export SONGMAKER_SUNO_COOKIE="your_cookie"
```

### 6.3 설정 확인

```bash
songmaker config show
```

---

## 7. YouTube 계정 인증 (썸네일 업로드용)

커스텀 썸네일을 업로드하려면 YouTube 계정이 전화번호로 인증되어야 한다.

```
1. https://youtube.com/verify 접속
2. 전화번호 입력 → SMS 인증 코드 수신
3. 인증 코드 입력 → 인증 완료
```

> **미인증 시**: 영상 업로드는 되지만 커스텀 썸네일 설정이 실패한다.
> 파이프라인은 중단되지 않고 YouTube 자동 생성 썸네일이 사용된다.

---

## 8. 설치 확인 체크리스트

```
[ ] Python 3.11+ 설치
[ ] Node.js 18+ 설치
[ ] FFmpeg + ffprobe 설치
[ ] YouTube API Key 발급
[ ] YouTube OAuth client_secret.json 다운로드
[ ] Gemini API Key 발급
[ ] Suno 유료 계정 (Pro/Premier) 가입
[ ] 2Captcha 계정 생성 + 잔액 충전 + API Key 확보
[ ] suno-api 클론 + Playwright 브라우저 설치
[ ] suno-api .env 설정 (쿠키 + 2Captcha Key)
[ ] suno-api 로컬 서버 실행 확인 (curl /api/get_limit)
[ ] YouTube 계정 전화번호 인증 (youtube.com/verify)
[ ] songmaker config 설정 완료
[ ] songmaker trend 정상 실행
```
