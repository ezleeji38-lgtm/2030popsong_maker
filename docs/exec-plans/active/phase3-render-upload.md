# Phase 3 — 렌더링 + 업로드 실행 계획

## 상태: 대기 (Phase 2 완료 후 시작)

---

## 목표

오디오 + 이미지를 MP4로 렌더링하고 YouTube에 업로드한다.

---

## 작업 목록

### Step 1: 영상 렌더링 (Stage 5)

```
[ ] renderer/ffmpeg.py
    - check_ffmpeg() — 설치 여부 확인
    - get_audio_duration(audio) — ffprobe로 길이 측정
    - lyrics_to_srt(lyrics, duration) — 가사 → SRT 변환
    - build_ffmpeg_command(...) — 명령어 조합
    - render(audio, background, output, options) — 실행
    - 진행 표시 (FFmpeg progress 파싱)

[ ] cli.py에 render 명령어 추가
    - songmaker render <song_id>
    - --subtitles 옵션
    - --fade 옵션
    - --resolution 옵션

[ ] Gate 5 검증 구현
    - FFmpeg 종료 코드
    - 파일 존재, 크기 범위
    - 비디오/오디오 스트림 검증
    - 길이, 해상도 검증 (비차단)
```

### Step 2: YouTube 업로드 (Stage 6)

```
[ ] uploader/youtube.py
    - authenticate(client_secret, token_path) — OAuth 2.0
    - upload(creds, video, metadata, thumbnail) — resumable upload
    - set_thumbnail(youtube, video_id, path)
    - set_public(creds, video_id) — 공개 전환
    - generate_title(song) → str
    - generate_description(song) → str
    - generate_tags(song) → list[str]

[ ] cli.py에 upload 명령어 추가
    - songmaker upload <song_id>
    - 업로드 후 공개 전환 확인 프롬프트

[ ] Gate 6 검증 구현
    - 인증 상태, 업로드 응답, URL 유효성
    - 공개 상태, 썸네일, 메타데이터 (비차단)
```

### Step 3: 통합 테스트

```
[ ] songmaker render <song_id> → video.mp4 생성
[ ] songmaker render <song_id> --subtitles → 자막 포함 렌더링
[ ] songmaker upload <song_id> → YouTube 비공개 업로드
[ ] Gate 5, Gate 6 검증 로그 확인
[ ] 업로드 후 공개 전환 테스트
```

---

## 완료 기준

- [ ] `songmaker render` → video.mp4 생성 + Gate 5 통과
- [ ] `songmaker upload` → YouTube URL 반환 + Gate 6 통과
- [ ] meta.json status == "uploaded"
- [ ] 비공개 업로드 + 사용자 확인 후 공개 전환

---

## 의존성

- Phase 2 완료 (audio.mp3 + background.png 존재)
- FFmpeg 로컬 설치
- Google Cloud Console에서 OAuth client_secret.json 발급
- YouTube 채널 보유

## 다음

Phase 3 완료 → Phase 4 (통합 + 배포) 진행
