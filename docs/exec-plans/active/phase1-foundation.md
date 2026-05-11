# Phase 1 — 기반 구축 + 트렌드 조사 실행 계획

## 상태: 대기

---

## 목표

CLI 뼈대를 완성하고 `songmaker trend` 명령어로 YouTube 인기 음악을 조회한다.

---

## 작업 목록

### Step 1: 프로젝트 스캐폴딩

```
[ ] pyproject.toml 작성
    - 패키지명: song-maker
    - Python >= 3.11
    - 의존성: typer, rich, google-api-python-client, google-auth-oauthlib,
              google-genai, httpx, pydantic, tomli-w
    - CLI 진입점: songmaker = song_maker.cli:app

[ ] 디렉토리 구조 생성
    - src/song_maker/__init__.py
    - src/song_maker/trend/__init__.py
    - src/song_maker/creator/__init__.py
    - src/song_maker/imager/__init__.py
    - src/song_maker/renderer/__init__.py
    - src/song_maker/uploader/__init__.py

[ ] .gitignore 작성
    - output/, *.env, config.toml, token.json, client_secret*.json
    - __pycache__/, *.pyc, .venv/
```

### Step 2: 공유 모듈

```
[ ] config.py
    - config_dir: ~/.songmaker/
    - load_config() → dict
    - save_config(config: dict)
    - config.toml 없으면 기본값으로 생성
    - 환경변수 오버라이드 지원

[ ] models.py (Pydantic BaseModel)
    - TrendItem (rank, title, artist, view_count, tags, video_id, published_at)
    - TrendReport (region, items, top_genres, top_keywords, fetched_at)
    - SongRequest (genre, mood, theme, lyrics_keywords, reference_song, count)
    - Song (id, genre, mood, theme, ..., status, gates, created_at)
    - Project (name, songs, output_dir)

[ ] gates.py
    - Check, GateResult (Pydantic BaseModel)
    - verify_gate1(report) → GateResult
    - run_gate(gate_fn, data, stage_name) → bool
    - handle_failure(result, stage_name) → 재시도/건너뛰기/중단
```

### Step 3: CLI 뼈대

```
[ ] cli.py
    - Typer 앱 초기화
    - songmaker trend 명령어 (빈 구현)
    - songmaker config 명령어
    - --verbose 글로벌 옵션
    - --version 옵션
```

### Step 4: 트렌드 조사

```
[ ] trend/youtube.py
    - fetch_trending(api_key, region, max_results) → list[TrendItem]
    - YouTube Data API v3 호출
    - 에러 처리 (403, 네트워크 등)

[ ] trend/analyzer.py
    - analyze(items) → TrendReport
    - 장르 매핑 테이블
    - 키워드 추출
    - print_report(report) — rich 테이블 출력
```

### Step 5: Gate 1 검증

```
[ ] 검증 함수 구현
    - verify_gate1(report) → GateResult
    - API 응답 검증
    - 결과 수 검증
    - 데이터 유효성 검증
```

### Step 6: 통합 테스트

```
[ ] songmaker config로 API 키 설정
[ ] songmaker trend 실행 → 한국 인기 음악 테이블 출력
[ ] songmaker trend --region US 실행 → 미국 인기 음악 출력
[ ] API 키 없이 실행 → 에러 메시지 확인
```

---

## 완료 기준

- [ ] `pip install -e .` 성공
- [ ] `songmaker --version` 출력
- [ ] `songmaker config` 으로 YouTube API 키 설정 가능
- [ ] `songmaker trend` 실행 시 인기 음악 테이블 출력
- [ ] Gate 1 검증 통과 로그 출력

---

## 의존성

- 없음 (첫 번째 Phase)

## 다음

Phase 1 완료 → Phase 2 (곡 생성 + 이미지 생성) 진행
