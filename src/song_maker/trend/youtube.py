"""YouTube Data API v3 호출. 트렌드 음악 조회 + Gate 1 검증."""

import time

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from song_maker.gates import Check, GateResult
from song_maker.models import TrendItem, TrendReport

MAX_RETRIES = 3
BACKOFF_SECONDS = [1, 2, 4]


def fetch_trending(
    api_key: str,
    region: str = "KR",
    max_results: int = 20,
) -> list[TrendItem]:
    """YouTube 인기 음악 차트를 조회한다.

    Args:
        api_key: YouTube Data API Key
        region: ISO 3166-1 alpha-2 지역 코드
        max_results: 최대 조회 수 (1~50)

    Returns:
        TrendItem 목록

    Raises:
        HttpError: API 호출 실패 (3회 재시도 후)
    """
    youtube = build("youtube", "v3", developerKey=api_key)

    for attempt in range(MAX_RETRIES):
        try:
            request = youtube.videos().list(
                part="snippet,statistics",
                chart="mostPopular",
                regionCode=region,
                videoCategoryId="10",  # Music
                maxResults=min(max_results, 50),
            )
            response = request.execute()
            break
        except HttpError as e:
            if attempt < MAX_RETRIES - 1 and e.resp.status in (429, 500, 503):
                time.sleep(BACKOFF_SECONDS[attempt])
                continue
            raise

    items: list[TrendItem] = []
    for index, item in enumerate(response.get("items", [])):
        snippet = item.get("snippet", {})
        statistics = item.get("statistics", {})

        # 필수 필드 누락 시 건너뜀
        title = snippet.get("title")
        artist = snippet.get("channelTitle")
        if not title or not artist:
            continue

        items.append(
            TrendItem(
                rank=index + 1,
                title=title,
                artist=artist,
                view_count=int(statistics.get("viewCount", 0)),
                tags=snippet.get("tags", []),
                video_id=item.get("id", ""),
                published_at=snippet.get("publishedAt", ""),
            )
        )

    return items


def verify_gate1(report: TrendReport) -> GateResult:
    """Gate 1: 트렌드 조사 결과 검증."""
    checks: list[Check] = []

    # 1-1. 결과 존재 (차단)
    checks.append(
        Check(
            name="result_count",
            passed=len(report.items) >= 1,
            blocking=True,
            message=f"트렌드 결과가 없습니다. (region={report.region})",
        )
    )

    # 1-2. 데이터 유효성 (차단)
    valid_items = sum(1 for item in report.items if item.title and item.artist)
    checks.append(
        Check(
            name="data_validity",
            passed=valid_items >= 1,
            blocking=True,
            message="유효한 트렌드 항목이 없습니다.",
        )
    )

    # 1-3. 분석 결과 (비차단)
    checks.append(
        Check(
            name="genre_analysis",
            passed=len(report.top_genres) >= 1,
            blocking=False,
            message="장르 분석 결과가 없습니다. 원시 데이터만 표시합니다.",
        )
    )

    # 1-4. 충분한 결과 수 (비차단)
    checks.append(
        Check(
            name="sufficient_results",
            passed=len(report.items) >= 5,
            blocking=False,
            message=f"트렌드 결과가 적습니다. ({len(report.items)}건)",
        )
    )

    return GateResult(gate="gate1", checks=checks)
