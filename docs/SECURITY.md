# Song Maker — Security Guide

## 1. API 키 관리

| 규칙 | 설명 |
|------|------|
| **저장 위치** | `~/.songmaker/config.toml` (사용자 홈 디렉토리) |
| **코드 내 금지** | API 키를 소스코드에 하드코딩하지 않는다 |
| **Git 제외** | `.gitignore`에 `config.toml`, `token.json`, `*.cookie` 포함 |
| **환경변수 지원** | `SONGMAKER_YOUTUBE_API_KEY` 등 환경변수로도 설정 가능 |

---

## 2. 인증 토큰

### YouTube OAuth 2.0
- 토큰 파일: `~/.songmaker/token.json`
- 최초 인증 시 브라우저를 통한 사용자 동의 필요
- refresh_token으로 자동 갱신
- 토큰 파일 권한: 소유자만 읽기/쓰기 (chmod 600)

### Suno 쿠키
- 쿠키 값: `~/.songmaker/config.toml` 내 `[suno].cookie`
- **~7일마다 만료** → 브라우저에서 suno.com 재로그인 후 쿠키 복사 필요
- 유료 계정(Pro/Premier)도 동일하게 만료됨
- 로그에 쿠키 값 출력 금지

### 2Captcha API Key
- API Key: `~/.songmaker/config.toml` 내 `[suno].twocaptcha_key`
- Suno가 hCaptcha를 요구하므로 **유료/무료 계정 무관하게 필수**
- 2Captcha 잔액 소진 시 곡 생성 불가
- 비용: hCaptcha ~$2.99/1,000건
- 로그에 API Key 출력 금지

---

## 3. 민감 파일 목록

`.gitignore`에 반드시 포함:
```
# API 키 및 인증
~/.songmaker/config.toml
~/.songmaker/token.json

# 프로젝트 내
*.env
config.toml
token.json
client_secret*.json
```

---

## 4. GitHub 배포 시 주의사항

| 항목 | 조치 |
|------|------|
| **config.toml** | `config.toml.example` 템플릿만 포함 (키 값 비움) |
| **client_secret.json** | 절대 커밋하지 않음. README에 발급 방법 안내 |
| **output/** | `.gitignore`에 포함. 생성물은 커밋하지 않음 |
| **커밋 전 검사** | `git diff --cached`로 민감 정보 포함 여부 확인 |

---

## 5. 외부 API 통신

| 규칙 | 설명 |
|------|------|
| **HTTPS만 사용** | 모든 API 호출은 HTTPS |
| **API 키 전송** | 헤더 또는 쿼리 파라미터 (각 API 규격 준수) |
| **에러 로깅** | API 응답에 포함된 키/토큰은 로그에서 마스킹 |
