# New User Onboarding

GitHub에서 Song Maker를 받은 사용자가 첫 곡을 업로드하기까지의 경로.

---

## 1. 최초 설치

```bash
git clone https://github.com/your-username/song-maker.git
cd song-maker
pip install -e .
songmaker --version
```

---

## 2. 사전 준비

상세는 [SETUP_GUIDE.md](../SETUP_GUIDE.md) 참조.

```
[ ] FFmpeg 설치
[ ] YouTube API Key 발급 + OAuth 클라이언트 설정
[ ] Gemini API Key 발급
[ ] Suno 계정 + suno-api 로컬 서버 설정
```

---

## 3. 설정

```bash
songmaker config
# YouTube API Key, Gemini API Key, Suno URL 입력

songmaker config show
# 설정 확인 (API 키는 마스킹)
```

---

## 4. 첫 실행

```bash
# 1. 트렌드 확인
songmaker trend

# 2. 전체 파이프라인 실행
songmaker run

# 대화형 입력 → 곡 생성 → 이미지 생성 → 렌더링 → 업로드
# 최초 업로드 시 브라우저에서 YouTube 인증 필요
```

---

## 5. 결과 확인

```bash
# 곡 목록
songmaker list

# 곡 상세 + Gate 검증 이력
songmaker status <song_id>

# 파일 확인
ls output/<project>/<song_id>/
# audio.mp3, lyrics.txt, background.png, thumbnail.png, video.mp4
```

---

## 6. 주의사항

- YouTube 업로드는 항상 **비공개**로 시작. 확인 후 공개 전환.
- suno-api 서버가 실행 중이어야 곡 생성 가능.
- YouTube API 일일 한도: 약 5곡 업로드/일.
- Gemini 무료 이미지: 하루 500장.
