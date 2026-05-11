# Phase 2 — 곡 생성 + 이미지 생성 실행 계획

## 상태: 대기 (Phase 1 완료 후 시작)

---

## 목표

사용자 입력을 받아 Suno로 곡을 생성하고, Gemini로 배경 이미지/썸네일을 생성한다.

---

## 작업 목록

### Step 1: 사용자 입력 (Stage 2)

```
[ ] cli.py에 create 명령어 추가
[ ] 대화형 입력 흐름 구현
    - 장르 선택 (트렌드 기반 목록 + 직접 입력)
    - 분위기 입력
    - 주제 입력
    - 가사 키워드 (선택)
    - 참고곡 (선택)
    - 곡 수
[ ] 입력 검증 (Gate 2)
[ ] 입력 확인 요약 테이블 출력
[ ] SongRequest 객체 생성
```

### Step 2: Suno 곡 생성 (Stage 3)

```
[ ] creator/prompt.py
    - build_suno_prompt(request) → dict
    - 장르/분위기 → 영문 태그 매핑 테이블
    - 모드 A (자동 가사) / 모드 B (키워드 기반)

[ ] creator/suno.py
    - suno-api 래퍼 연동 방식 결정 및 구현
    - generate(prompt) → task_id
    - poll_status(task_id) → status (5초 간격, 5분 타임아웃)
    - download(song_data, output_dir) → (audio_path, lyrics_path)
    - 진행 표시 (rich Progress)

[ ] output 저장 구조 구현
    - output/{project}/{song_id}/ 디렉토리 생성
    - meta.json 저장

[ ] Gate 3 검증 구현
    - 파일 존재, 크기, 오디오 무결성
```

### Step 3: Gemini 이미지 생성 (Stage 4)

```
[ ] imager/prompt.py
    - build_image_prompt(song) → str
    - build_thumbnail_prompt(song) → str
    - 장르/분위기 → 시각 스타일 매핑 테이블

[ ] imager/gemini.py
    - google-genai SDK 연동
    - generate_image(prompt, output_path, model) → Path
    - fallback 모델 전환 로직
    - 진행 표시

[ ] Gate 4 검증 구현
    - 파일 존재, 크기, PNG 디코딩, 해상도
    - 썸네일 fallback (배경 복사)
```

### Step 4: 파이프라인 연결

```
[ ] cli.py에서 Stage 2 → Gate 2 → Stage 3 → Gate 3 → Stage 4 → Gate 4 연결
[ ] songmaker image <song_id> 명령어 (Stage 4만 단독 실행)
[ ] 다중 곡 생성 (count > 1) 지원
```

### Step 5: 통합 테스트

```
[ ] songmaker create 실행 → 입력 → 곡 생성 → 이미지 생성
[ ] output/ 디렉토리 확인: audio.mp3, lyrics.txt, background.png, thumbnail.png
[ ] meta.json 상태 확인: "imaged"
[ ] Gate 3, Gate 4 검증 로그 확인
[ ] 실패 시나리오 테스트 (API 에러, 타임아웃)
```

---

## 완료 기준

- [ ] `songmaker create` → 대화형 입력 동작
- [ ] Suno API 호출 → audio.mp3 + lyrics.txt 저장
- [ ] Gemini API 호출 → background.png + thumbnail.png 저장
- [ ] Gate 2, 3, 4 검증 모두 통과
- [ ] meta.json status == "imaged"

---

## 의존성

- Phase 1 완료 (CLI 뼈대, config, models)
- Suno 계정 + suno-api 로컬 서버 실행
- Google AI API Key (Gemini)

## 다음

Phase 2 완료 → Phase 3 (렌더링 + 업로드) 진행
