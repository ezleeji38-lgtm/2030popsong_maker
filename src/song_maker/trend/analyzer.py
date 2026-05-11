"""트렌드 분석 및 CLI 출력."""

from collections import Counter

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from song_maker.models import TrendItem, TrendReport

console = Console()

# 태그 → 장르 매핑
GENRE_MAP: dict[str, list[str]] = {
    "발라드": ["ballad", "발라드", "slow", "감성"],
    "K-pop": ["kpop", "k-pop", "케이팝", "아이돌", "idol"],
    "힙합": ["hiphop", "hip-hop", "힙합", "rap", "랩"],
    "댄스": ["dance", "댄스", "edm", "electronic"],
    "인디": ["indie", "인디", "acoustic", "어쿠스틱"],
    "R&B": ["rnb", "r&b", "soul", "소울"],
    "록": ["rock", "록", "band", "밴드"],
    "트로트": ["trot", "트로트"],
    "팝": ["pop", "팝"],
}

# 제외할 일반적 태그
STOPWORDS = {
    "music", "mv", "official", "video", "lyrics", "audio",
    "뮤직", "뮤직비디오", "가사", "오피셜", "공식",
}


def _classify_genre(tags: list[str]) -> list[str]:
    """태그 목록에서 장르를 추출한다."""
    tags_lower = [t.lower() for t in tags]
    genres = []
    for genre, keywords in GENRE_MAP.items():
        if any(kw in tag for tag in tags_lower for kw in keywords):
            genres.append(genre)
    return genres if genres else ["기타"]


def _extract_keywords(items: list[TrendItem], top_n: int = 10) -> list[str]:
    """전체 태그에서 빈출 키워드를 추출한다."""
    counter: Counter[str] = Counter()
    for item in items:
        for tag in item.tags:
            tag_lower = tag.lower().strip()
            if tag_lower and tag_lower not in STOPWORDS and len(tag_lower) > 1:
                counter[tag_lower] += 1
    return [word for word, _ in counter.most_common(top_n)]


def analyze(items: list[TrendItem], region: str = "KR") -> TrendReport:
    """트렌드 항목을 분석하여 TrendReport를 생성한다."""
    genre_counter: Counter[str] = Counter()
    for item in items:
        genres = _classify_genre(item.tags)
        for g in genres:
            genre_counter[g] += 1

    top_genres = [genre for genre, _ in genre_counter.most_common(5)]
    top_keywords = _extract_keywords(items)

    return TrendReport(
        region=region,
        items=items,
        top_genres=top_genres,
        top_keywords=top_keywords,
    )


def _format_views(count: int) -> str:
    """조회수를 읽기 쉬운 형태로 변환."""
    if count >= 1_000_000_000:
        return f"{count / 1_000_000_000:.1f}B"
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}K"
    return str(count)


def print_report(report: TrendReport) -> None:
    """트렌드 보고서를 CLI 테이블로 출력한다."""
    table = Table(title=f"유튜브 인기 음악 ({report.region})")
    table.add_column("#", justify="right", width=4)
    table.add_column("제목", width=30)
    table.add_column("아티스트", width=15)
    table.add_column("조회수", justify="right", width=10)
    table.add_column("태그", width=25)

    for item in report.items:
        tags_str = ", ".join(item.tags[:3]) if item.tags else "-"
        if len(tags_str) > 25:
            tags_str = tags_str[:22] + "..."

        table.add_row(
            str(item.rank),
            item.title[:30],
            item.artist[:15],
            _format_views(item.view_count),
            tags_str,
        )

    console.print(table)

    if report.top_genres:
        console.print(Panel(
            f"주요 장르: {', '.join(report.top_genres)}",
            title="트렌드 분석",
            border_style="cyan",
        ))

    if report.top_keywords:
        console.print(Panel(
            f"키워드: {', '.join(report.top_keywords[:8])}",
            border_style="dim",
        ))
