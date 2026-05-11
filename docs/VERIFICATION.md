# Song Maker — Verification Gate Design

## 1. 개요

Song Maker는 6단계 파이프라인이다. 각 Stage 사이에 **검증 게이트(Verification Gate)**를 두어, 출력물이 기준을 통과해야만 다음 Stage로 진행한다. 검증 실패 시 자동 재시도, 사용자 판단, 또는 중단으로 분기한다.

```
Stage 1 → [Gate 1] → Stage 2 → [Gate 2] → Stage 3 → [Gate 3] → Stage 4 → [Gate 4] → Stage 5 → [Gate 5] → Stage 6 → [Gate 6]
트렌드     검증      사용자      검증      곡 생성     검증      이미지      검증      렌더링      검증      업로드      검증
```

---

## 2. 검증 게이트 상세

### Gate 1 — 트렌드 조사 후

**검증 시점**: `trend/youtube.py` → `trend/analyzer.py` 실행 완료 후

| # | 검증 항목 | 통과 조건 | 실패 시 |
|---|----------|-----------|---------|
| 1-1 | API 응답 수신 | HTTP 200, 응답 본문 존재 | 재시도 (3회) → 실패 시 중단 |
| 1-2 | 결과 수 | `len(items) >= 1` | 지역 변경 제안 → 사용자 판단 |
| 1-3 | 데이터 유효성 | 각 item에 title, channelTitle 존재 | 해당 item 제외, 나머지 진행 |
| 1-4 | 분석 결과 | `len(top_genres) >= 1` | 장르 분석 건너뜀, 원시 데이터만 표시 |

**실패 분기 흐름:**
```
API 실패 ──→ 재시도 (1초, 2초, 4초) ──→ 3회 실패 ──→ [중단]
                                                      "YouTube API 호출 실패. 네트워크 또는 API 키를 확인하세요."

결과 0건 ──→ [사용자 판단]
              "해당 지역에 트렌드 데이터가 없습니다."
              "? 다른 지역으로 조회하시겠습니까? (US/JP/KR): "
```

---

### Gate 2 — 사용자 입력 후

**검증 시점**: 사용자가 장르/분위기/주제 입력 완료 후

| # | 검증 항목 | 통과 조건 | 실패 시 |
|---|----------|-----------|---------|
| 2-1 | 필수 입력 | genre, mood, theme 모두 비어있지 않음 | 재입력 요청 |
| 2-2 | 곡 수 범위 | `1 <= count <= 10` | 범위 안내 후 재입력 |
| 2-3 | 참고곡 번호 | 트렌드 목록 범위 내 | "유효하지 않은 번호" 안내 후 재입력 |

**실패 분기 흐름:**
```
필수 입력 누락 ──→ "장르를 입력해주세요." ──→ 재입력 (무한 반복 허용)

곡 수 초과 ──→ "1~10 사이로 입력해주세요." ──→ 재입력
```

---

### Gate 3 — 곡 생성 후

**사전 검증** (Stage 3 실행 전):

| # | 검증 항목 | 통과 조건 | 실패 시 |
|---|----------|-----------|---------|
| 3-pre-1 | suno-api 서버 | `GET /api/get_limit` 응답 200 | "suno-api 서버가 응답하지 않습니다" → 중단 |
| 3-pre-2 | 2Captcha 잔액 | 잔액 > $0.10 | "2Captcha 잔액 부족 (${balance}). 충전 후 재시도하세요" → 중단 |
| 3-pre-3 | 쿠키 유효성 | `/api/get_limit` 결과에 크레딧 정보 존재 | "Suno 쿠키가 만료되었습니다. 갱신 후 재시도하세요" → 쿠키 갱신 안내 |

**검증 시점**: `creator/suno.py` → 오디오 다운로드 완료 후

| # | 검증 항목 | 통과 조건 | 실패 시 |
|---|----------|-----------|---------|
| 3-1 | API 응답 | Suno API에서 task_id 수신 | 재시도 (3회) → 실패 시 `songmaker import` 안내 |
| 3-2 | 생성 완료 | 폴링 결과 status == "complete" | 타임아웃(5분) → 사용자 판단 |
| 3-3 | 파일 존재 | `audio.mp3` 파일 존재 | 재다운로드 시도 → 실패 시 중단 |
| 3-4 | 파일 크기 | `audio.mp3` > 100KB | "비정상 파일" 경고 → 재생성 제안 |
| 3-5 | 오디오 무결성 | ffprobe로 오디오 스트림 감지 | "손상된 파일" → 재생성 제안 |
| 3-6 | 가사 존재 | `lyrics.txt` 파일 존재, 비어있지 않음 | 경고 출력, 가사 없이 진행 (비차단) |

**실패 분기 흐름:**
```
사전 체크 ──→ suno-api 서버 미응답 → [중단] "suno-api 서버를 시작하세요."
          ──→ 2Captcha 잔액 부족  → [중단] "2Captcha 잔액을 충전하세요."
          ──→ 쿠키 만료           → [중단] "Suno 쿠키를 갱신하세요. (SETUP_GUIDE.md 5.5 참조)"

API 실패 ──→ 재시도 (5초, 10초, 20초) ──→ 3회 실패 ──→ [사용자 판단]
              "Suno API 곡 생성 실패."
              "? 재시도 / 수동 임포트(songmaker import) / 중단 (r/i/q): "

타임아웃 ──→ [사용자 판단]
              "곡 생성이 5분을 초과했습니다."
              "? 계속 대기 / 재시도 / 중단 (w/r/q): "

파일 손상 ──→ [사용자 판단]
              "오디오 파일이 손상되었을 수 있습니다. (크기: 52KB)"
              "? 재생성 / 그래도 진행 / 중단 (r/c/q): "
```

**검증 코드 구조:**
```python
def verify_gate3(song: Song) -> GateResult:
    checks = []

    # 3-3. 파일 존재
    checks.append(Check(
        name="audio_file_exists",
        passed=song.audio_path.exists(),
        message="오디오 파일이 존재하지 않습니다."
    ))

    # 3-4. 파일 크기
    if song.audio_path.exists():
        size = song.audio_path.stat().st_size
        checks.append(Check(
            name="audio_file_size",
            passed=size > 100_000,
            message=f"오디오 파일이 비정상적으로 작습니다. ({size // 1000}KB)"
        ))

    # 3-5. 오디오 무결성
    checks.append(Check(
        name="audio_integrity",
        passed=ffprobe_has_audio_stream(song.audio_path),
        message="오디오 스트림을 감지할 수 없습니다."
    ))

    # 3-6. 가사 존재 (비차단)
    checks.append(Check(
        name="lyrics_exists",
        passed=song.lyrics_path.exists() and song.lyrics_path.stat().st_size > 0,
        blocking=False,
        message="가사 파일이 없습니다. 가사 없이 진행합니다."
    ))

    return GateResult(gate="gate3", checks=checks)
```

---

### Gate 4 — 이미지 생성 후

**검증 시점**: `imager/gemini.py` → 이미지 저장 완료 후

| # | 검증 항목 | 통과 조건 | 실패 시 |
|---|----------|-----------|---------|
| 4-1 | API 응답 | Gemini API 200 응답 + 이미지 데이터 존재 | 재시도 → fallback 모델 → 실패 시 중단 |
| 4-2 | 배경 파일 존재 | `background.png` 존재 | 재생성 시도 |
| 4-3 | 배경 파일 크기 | `background.png` > 10KB | "비정상 이미지" → 재생성 제안 |
| 4-4 | 이미지 디코딩 | PNG 파일로 정상 디코딩 가능 | 재생성 시도 |
| 4-5 | 해상도 확인 | 너비 >= 1920, 높이 >= 1080 | 경고 출력, 진행 (비차단) |
| 4-6 | 썸네일 파일 | `thumbnail.png` 존재 + 크기 > 10KB | 경고 출력, 배경 이미지를 썸네일로 복사 (비차단) |

**실패 분기 흐름:**
```
API 실패 ──→ 재시도 (2초, 4초, 8초)
          ──→ fallback 모델 (gemini-3-pro-image-preview) 시도
          ──→ 실패 시 [사용자 판단]
              "이미지 생성에 실패했습니다."
              "? 재시도 / 직접 이미지 지정 / 기본 배경 사용 / 중단 (r/s/d/q): "

썸네일 실패 ──→ 배경 이미지를 썸네일로 자동 복사
              "[경고] 썸네일 생성 실패. 배경 이미지를 썸네일로 사용합니다."
```

**이미지 검증 코드 구조:**
```python
def verify_gate4(song: Song) -> GateResult:
    checks = []

    # 4-2, 4-3. 배경 파일
    bg = song.background_path
    checks.append(Check(
        name="background_exists",
        passed=bg.exists() and bg.stat().st_size > 10_000,
        message="배경 이미지가 없거나 비정상적입니다."
    ))

    # 4-4. 이미지 디코딩
    checks.append(Check(
        name="background_decodable",
        passed=can_decode_png(bg),
        message="배경 이미지를 디코딩할 수 없습니다."
    ))

    # 4-5. 해상도 (비차단)
    w, h = get_image_dimensions(bg)
    checks.append(Check(
        name="background_resolution",
        passed=w >= 1920 and h >= 1080,
        blocking=False,
        message=f"해상도가 권장 기준 미달입니다. ({w}x{h})"
    ))

    # 4-6. 썸네일 (비차단)
    checks.append(Check(
        name="thumbnail_exists",
        passed=song.thumbnail_path.exists() and song.thumbnail_path.stat().st_size > 10_000,
        blocking=False,
        message="썸네일 생성 실패. 배경 이미지를 썸네일로 사용합니다.",
        fallback=lambda: shutil.copy(bg, song.thumbnail_path)
    ))

    return GateResult(gate="gate4", checks=checks)
```

---

### Gate 5 — 영상 렌더링 후

**검증 시점**: `renderer/ffmpeg.py` → MP4 생성 완료 후

| # | 검증 항목 | 통과 조건 | 실패 시 |
|---|----------|-----------|---------|
| 5-1 | FFmpeg 종료 코드 | exit code == 0 | 에러 로그 표시 → 사용자 판단 |
| 5-2 | 파일 존재 | `video.mp4` 존재 | 재렌더링 시도 |
| 5-3 | 파일 크기 | 1MB < `video.mp4` < 500MB | "비정상 크기" → 사용자 판단 |
| 5-4 | 비디오 스트림 | ffprobe로 비디오 스트림(H.264) 감지 | 재렌더링 시도 |
| 5-5 | 오디오 스트림 | ffprobe로 오디오 스트림(AAC) 감지 | 재렌더링 시도 |
| 5-6 | 영상 길이 | 오디오 길이와 ±2초 이내 | 경고 출력 (비차단) |
| 5-7 | 해상도 | ffprobe 출력 해상도 == 설정 해상도 | 경고 출력 (비차단) |

**실패 분기 흐름:**
```
FFmpeg 에러 ──→ stderr 로그 표시
             ──→ [사용자 판단]
                 "렌더링 실패. FFmpeg 에러:"
                 "  {stderr 마지막 5줄}"
                 "? 재시도 / 옵션 변경 / 중단 (r/o/q): "

비정상 크기 ──→ [사용자 판단]
               "영상 크기가 비정상적입니다. ({size}MB)"
               "? 그래도 진행 / 재렌더링 / 중단 (c/r/q): "
```

**렌더링 검증 코드 구조:**
```python
def verify_gate5(song: Song) -> GateResult:
    checks = []
    video = song.video_path

    # 5-2. 파일 존재
    checks.append(Check(
        name="video_exists",
        passed=video.exists(),
        message="영상 파일이 생성되지 않았습니다."
    ))

    # 5-3. 파일 크기
    if video.exists():
        size_mb = video.stat().st_size / (1024 * 1024)
        checks.append(Check(
            name="video_size",
            passed=1 < size_mb < 500,
            message=f"영상 크기가 비정상적입니다. ({size_mb:.1f}MB)"
        ))

    # 5-4, 5-5. 스트림 검증
    probe = ffprobe_info(video)
    checks.append(Check(
        name="video_stream",
        passed=probe.has_video and probe.video_codec == "h264",
        message="비디오 스트림(H.264)을 감지할 수 없습니다."
    ))
    checks.append(Check(
        name="audio_stream",
        passed=probe.has_audio and probe.audio_codec == "aac",
        message="오디오 스트림(AAC)을 감지할 수 없습니다."
    ))

    # 5-6. 길이 비교 (비차단)
    audio_dur = get_audio_duration(song.audio_path)
    checks.append(Check(
        name="duration_match",
        passed=abs(probe.duration - audio_dur) <= 2.0,
        blocking=False,
        message=f"영상({probe.duration:.1f}초)과 오디오({audio_dur:.1f}초) 길이 차이"
    ))

    return GateResult(gate="gate5", checks=checks)
```

---

### Gate 6 — 유튜브 업로드 후

**검증 시점**: `uploader/youtube.py` → 업로드 완료 후

| # | 검증 항목 | 통과 조건 | 실패 시 |
|---|----------|-----------|---------|
| 6-1 | 인증 상태 | OAuth 토큰 유효 | 브라우저 재인증 요청 |
| 6-2 | 업로드 응답 | API 200 + video_id 반환 | 재시도 (2회) → 실패 시 중단 |
| 6-3 | 영상 URL | YouTube URL 형식 유효 | 에러 로깅 + 중단 |
| 6-4 | 공개 상태 | 비공개로 설정되었는가 | 경고 출력 (비차단) |
| 6-5 | 썸네일 설정 | 썸네일 업로드 성공 | 경고 출력, 기본 썸네일 사용 (비차단) |
| 6-6 | 메타데이터 | 제목/설명/태그가 설정되었는가 | 경고 출력 (비차단) |

**실패 분기 흐름:**
```
인증 만료 ──→ "YouTube 인증이 만료되었습니다."
           ──→ 자동 refresh 시도
           ──→ 실패 시 브라우저 재인증 안내

업로드 실패 ──→ 재시도 (10초, 20초)
            ──→ 2회 실패 시 [중단]
               "YouTube 업로드에 실패했습니다."
               "영상 파일: output/.../video.mp4"
               "수동 업로드 후 songmaker status로 상태를 업데이트할 수 있습니다."
```

---

## 3. 검증 공통 구조

### 3.1 Check / GateResult 모델

```python
# gates.py (Pydantic BaseModel 사용)

class Check(BaseModel):
    name: str               # 검증 항목 ID
    passed: bool            # 통과 여부
    blocking: bool = True   # True: 실패 시 중단, False: 경고만
    message: str = ""       # 실패 시 표시 메시지

class GateResult(BaseModel):
    gate: str               # gate1 ~ gate6
    checks: list[Check]
    timestamp: datetime

    @property
    def passed(self) -> bool:
        """차단(blocking) 검증이 모두 통과했는가"""
        return all(c.passed for c in self.checks if c.blocking)

    @property
    def warnings(self) -> list[Check]:
        """비차단 검증 중 실패한 항목"""
        return [c for c in self.checks if not c.blocking and not c.passed]

    @property
    def failures(self) -> list[Check]:
        """차단 검증 중 실패한 항목"""
        return [c for c in self.checks if c.blocking and not c.passed]
```

> `fallback` 동작(예: 썸네일 실패 시 배경 복사)은 `gates.py` 내
> `run_gate()` 함수에서 Gate별로 하드코딩한다. 직렬화 불가능한
> Callable을 모델에 넣지 않는다.

### 3.2 게이트 실행 흐름

```python
def run_gate(gate_fn, song, stage_name) -> bool:
    result = gate_fn(song)
    log_gate_result(result)

    # 비차단 경고 처리
    for warn in result.warnings:
        console.print(f"[경고] {warn.message}")
        if warn.fallback:
            warn.fallback()

    # 차단 실패 처리
    if not result.passed:
        for fail in result.failures:
            console.print(f"[실패] {fail.message}")
        return handle_failure(result, stage_name)

    console.print(f"[통과] {stage_name} 검증 완료")
    return True
```

### 3.3 실패 처리 분기

```python
def handle_failure(result: GateResult, stage_name: str) -> bool:
    """
    실패 유형에 따라 분기:
    - retry:  자동 재시도 (API 호출 실패 등)
    - ask:    사용자 판단 요청 (품질 문제 등)
    - abort:  즉시 중단 (치명적 오류)
    """
    action = prompt_user(
        f"{stage_name} 검증 실패. 어떻게 하시겠습니까?",
        choices=["재시도(r)", "건너뛰기(s)", "중단(q)"]
    )

    if action == "r":
        return RETRY
    elif action == "s":
        return SKIP
    else:
        return ABORT
```

---

## 4. 검증 로그

### 4.1 로그 저장

각 게이트 실행 결과를 `meta.json`에 기록한다.

```json
{
  "id": "a1b2c3",
  "status": "rendered",
  "gates": {
    "gate1": {
      "passed": true,
      "timestamp": "2026-03-31T10:00:01",
      "checks": [
        {"name": "api_response", "passed": true},
        {"name": "result_count", "passed": true},
        {"name": "data_validity", "passed": true}
      ]
    },
    "gate3": {
      "passed": true,
      "timestamp": "2026-03-31T10:01:30",
      "checks": [
        {"name": "audio_file_exists", "passed": true},
        {"name": "audio_file_size", "passed": true},
        {"name": "audio_integrity", "passed": true},
        {"name": "lyrics_exists", "passed": false, "blocking": false}
      ],
      "warnings": ["가사 파일이 없습니다. 가사 없이 진행합니다."]
    },
    "gate5": {
      "passed": false,
      "timestamp": "2026-03-31T10:03:00",
      "failures": ["비디오 스트림(H.264)을 감지할 수 없습니다."],
      "action_taken": "retry"
    }
  }
}
```

### 4.2 CLI 검증 요약 출력

`songmaker status <song_id>` 실행 시 검증 이력 표시:

```
$ songmaker status a1b2c3

  곡 상태: a1b2c3
┌────────┬────────┬──────────────────────┬──────────────────────────┐
│ Gate   │ 결과   │ 시간                 │ 비고                     │
├────────┼────────┼──────────────────────┼──────────────────────────┤
│ Gate 1 │ 통과   │ 2026-03-31 10:00:01  │                          │
│ Gate 2 │ 통과   │ 2026-03-31 10:00:15  │                          │
│ Gate 3 │ 통과   │ 2026-03-31 10:01:30  │ 경고: 가사 없음          │
│ Gate 4 │ 통과   │ 2026-03-31 10:02:10  │                          │
│ Gate 5 │ 실패→통과│ 2026-03-31 10:03:00 │ 1회 재시도 후 통과       │
│ Gate 6 │ 대기   │ -                    │                          │
└────────┴────────┴──────────────────────┴──────────────────────────┘
```

---

## 5. 검증 게이트 요약표

| Gate | 위치 | 차단 검증 수 | 비차단 검증 수 | 핵심 판정 기준 |
|------|------|-------------|---------------|---------------|
| Gate 1 | 트렌드 조사 후 | 2 | 2 | API 응답 + 결과 존재 |
| Gate 2 | 사용자 입력 후 | 3 | 0 | 필수 입력 완료 |
| Gate 3 | 곡 생성 후 | 4 | 1 | 오디오 파일 존재 + 무결성 |
| Gate 4 | 이미지 생성 후 | 3 | 3 | 배경 이미지 존재 + 디코딩 |
| Gate 5 | 렌더링 후 | 4 | 3 | 영상 파일 + 스트림 검증 |
| Gate 6 | 업로드 후 | 3 | 3 | 업로드 성공 + URL 반환 |
| **합계** | | **19** | **12** | |
