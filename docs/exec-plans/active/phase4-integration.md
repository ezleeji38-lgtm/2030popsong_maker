# Phase 4 — 통합 + 배포 실행 계획

## 상태: 대기 (Phase 3 완료 후 시작)

---

## 목표

전체 파이프라인을 `songmaker run` 하나로 통합하고, GitHub 배포를 준비한다.

---

## 작업 목록

### Step 1: 전체 파이프라인 통합

```
[ ] cli.py에 run 명령어 구현
    - Stage 1 → Gate 1 → Stage 2 → Gate 2 → Stage 3 → Gate 3
      → Stage 4 → Gate 4 → Stage 5 → Gate 5 → Stage 6 → Gate 6
    - 각 Gate 실패 시 분기 처리 (재시도/건너뛰기/중단)
    - --count 옵션으로 다중 곡 생성

[ ] 파이프라인 중간 재개
    - meta.json의 status를 확인하여 마지막 완료 Stage부터 재개
    - songmaker run --resume <song_id>
```

### Step 2: 관리 명령어

```
[ ] songmaker list
    - output/ 내 모든 곡 목록 표시
    - ID, 주제, 장르, 상태, 생성일
    - rich 테이블 출력

[ ] songmaker status <song_id>
    - 곡 상세 정보 + Gate 검증 이력
    - 각 Gate 통과/실패 시간 표시

[ ] songmaker config show
    - 현재 설정 표시 (API 키는 마스킹)
```

### Step 3: 배치 처리

```
[ ] count > 1 시 전체 흐름
    - Stage 2에서 1회 입력 → count만큼 곡 생성
    - 각 곡마다 Stage 3~6 반복
    - 진행 표시: "곡 2/5 처리 중..."
    - 개별 곡 실패 시 해당 곡만 건너뛰고 나머지 계속

[ ] 배치 결과 요약
    - 전체 곡 수, 성공, 실패, 업로드 URL 목록
```

### Step 4: GitHub 배포 준비

```
[ ] README.md 작성
    - 프로젝트 소개
    - 설치 방법 (pip install)
    - 사전 준비 (API 키 발급, FFmpeg 설치)
    - 사용법 (명령어 예시)
    - 설정 파일 설명

[ ] config.toml.example 작성
    - API 키 빈 값으로 템플릿 제공

[ ] .gitignore 최종 정리

[ ] LICENSE 파일 추가

[ ] pyproject.toml 최종 검증
    - pip install . 테스트
    - songmaker --help 동작 확인
```

### Step 5: 최종 통합 테스트

```
[ ] 클린 환경에서 테스트
    1. git clone
    2. pip install .
    3. songmaker config → API 키 설정
    4. songmaker run → 전체 파이프라인 실행
    5. songmaker list → 곡 목록 확인
    6. songmaker status <id> → 상태 + 검증 이력 확인

[ ] 에러 시나리오 테스트
    - API 키 없이 실행
    - FFmpeg 없이 렌더링
    - 네트워크 끊김 상태
    - Suno 서버 미실행 상태
```

---

## 완료 기준

- [ ] `songmaker run` → Stage 1~6 + Gate 1~6 전체 동작
- [ ] `songmaker list` + `songmaker status` 동작
- [ ] 배치 생성 (count > 1) 동작
- [ ] `pip install .` → 클린 환경에서 설치 + 실행 성공
- [ ] README.md, .gitignore, LICENSE 완비
- [ ] GitHub push 준비 완료

---

## 의존성

- Phase 1~3 모두 완료

## 다음

Phase 4 완료 → GitHub 저장소 공개 → v1.0 릴리스
