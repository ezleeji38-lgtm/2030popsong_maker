# Stage 1 — 트렌드 조사 상세 설계

## 1. 목적

YouTube 인기 음악 차트를 조회하여 현재 트렌드(장르, 분위기, 키워드)를 분석하고 사용자에게 보고한다.

---

## 2. 모듈 구성

```
trend/
├── __init__.py
├── youtube.py      # YouTube Data API v3 호출
└── analyzer.py     # 트렌드 분석 및 출력
```

---

## 3. youtube.py 상세

### 함수

```python
def fetch_trending(
    api_key: str,
    region: str = "KR",
    max_results: int = 20
) -> list[TrendItem]:
```

### API 호출 구성

```python
youtube = build("youtube", "v3", developerKey=api_key)

request = youtube.videos().list(
    part="snippet,statistics",
    chart="mostPopular",
    regionCode=region,
    videoCategoryId="10",      # Music
    maxResults=max_results
)
response = request.execute()
```

### 응답 파싱

```python
for index, item in enumerate(response["items"]):
    TrendItem(
        rank=index + 1,
        title=item["snippet"]["title"],
        artist=item["snippet"]["channelTitle"],
        view_count=int(item["statistics"]["viewCount"]),
        tags=item["snippet"].get("tags", []),
        video_id=item["id"],
        published_at=item["snippet"]["publishedAt"],   # 모델에 포함됨
    )
```

### 에러 처리

| 에러 | HTTP 코드 | 처리 |
|------|----------|------|
| API 키 무효 | 403 | "API 키가 유효하지 않습니다" → 중단 |
| 할당량 초과 | 403 | "일일 할당량 초과" → 중단 |
| 네트워크 오류 | - | 재시도 3회 (지수 백오프) |
| 결과 없음 | 200 | Gate 1에서 처리 |

---

## 4. analyzer.py 상세

### 함수

```python
def analyze(items: list[TrendItem]) -> TrendReport:
```

### 장르 매핑 테이블

태그에서 장르를 추출하기 위한 키워드 매핑:

```python
GENRE_MAP = {
    "발라드": ["ballad", "발라드", "slow", "감성"],
    "K-pop": ["kpop", "k-pop", "케이팝", "아이돌"],
    "힙합": ["hiphop", "hip-hop", "힙합", "rap", "랩"],
    "댄스": ["dance", "댄스", "edm", "electronic"],
    "인디": ["indie", "인디", "acoustic", "어쿠스틱"],
    "R&B": ["rnb", "r&b", "soul", "소울"],
    "록": ["rock", "록", "band", "밴드"],
    "트로트": ["trot", "트로트"],
}
```

### 분석 로직

```
1. 각 TrendItem의 tags를 순회
2. GENRE_MAP과 대조하여 장르 분류
3. 분류된 장르의 빈도 집계 → top_genres
4. 태그 중 빈출 단어 추출 → top_keywords
5. TrendReport 객체 생성
```

### CLI 출력

`rich` 라이브러리의 `Table`과 `Panel` 사용:

```python
def print_report(report: TrendReport):
    table = Table(title="유튜브 인기 음악")
    table.add_column("#", width=4)
    table.add_column("제목", width=25)
    table.add_column("아티스트", width=12)
    table.add_column("조회수", width=10, justify="right")
    table.add_column("태그", width=20)

    for item in report.items:
        table.add_row(...)

    console.print(table)
    console.print(Panel(f"주요 장르: {', '.join(report.top_genres)}"))
    console.print(Panel(f"키워드: {', '.join(report.top_keywords)}"))
```

---

## 5. Gate 1 검증 연계

이 Stage 완료 후 Gate 1이 실행된다:
- API 응답 수신 여부
- 결과 1건 이상 존재 여부
- 각 item 데이터 유효성
- 분석 결과 존재 여부

Gate 1 통과 시 → Stage 2 (사용자 입력)로 진행.
