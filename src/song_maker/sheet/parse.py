"""챗봇 출력 텍스트 → 시트 행 dict 파싱.

지원 포맷 (지침서 Section 16 권장 출력 양식 + 유연한 변형):

  TITLE: Midnight Replay
  TAGS: 95 BPM, Modern Pop, Female vocal, nostalgic
  LYRICS:
  [Intro]
  ...
  [Outro]

또는 마크다운/이모지 prefix가 붙어도 인식:
  ## TITLE: ...
  **TAGS:** ...
  🎵 LYRICS:

대소문자 무시, 공백 무시, 콜론 후 즉시 본문.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# field 이름 매칭 (유연하게). prefix는 마크다운 #*, 이모지, > 등 흔한 것들 허용.
_FIELD_PATTERNS = {
    "title": re.compile(r"^[\s#*🎵>📝-]*\s*title\s*\**\s*[:：]\s*(.+?)\s*$", re.IGNORECASE),
    "tags": re.compile(r"^[\s#*🎵>📝-]*\s*(?:tags|style|prompt|suno)\s*\**\s*[:：]\s*(.+?)\s*$", re.IGNORECASE),
    "lyrics": re.compile(r"^[\s#*🎵>📝-]*\s*lyrics\s*\**\s*[:：]?\s*$", re.IGNORECASE),
    "persona_id": re.compile(r"^[\s#*🎵>📝-]*\s*persona[_ ]?id\s*\**\s*[:：]\s*(.+?)\s*$", re.IGNORECASE),
}


def _clean_value(v: str) -> str:
    r"""마크다운 ** 같은 양끝 장식 제거.

    `**100 BPM**`, `**100 BPM` (한쪽만), `*100 BPM*` 등 마크다운 강조 문자 제거.
    """
    s = v.strip()
    # 시작/끝의 `*`, `_`, ` 반복 제거 (양쪽 독립적으로)
    while s and s[0] in "*_`":
        s = s[1:]
    while s and s[-1] in "*_`":
        s = s[:-1]
    return s.strip()


@dataclass
class ParsedRow:
    title: str = ""
    tags: str = ""
    lyrics: str = ""
    persona_id: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "title": self.title,
            "tags": self.tags,
            "lyrics": self.lyrics,
            "persona_id": self.persona_id,
        }

    def is_complete(self) -> bool:
        return bool(self.title and self.tags and self.lyrics)


def parse_chatbot_output(text: str) -> ParsedRow:
    """챗봇 출력 텍스트에서 title/tags/lyrics/persona_id 추출.

    - TITLE: 첫 줄에 매칭되는 패턴
    - TAGS: 같은 라인에 매칭
    - LYRICS: 라인 자체가 LYRICS:면 그 이후 모든 줄을 가사로 (다음 인식되는 필드 라인 전까지)
    - persona_id: 선택, 매칭되면 추출
    """
    parsed = ParsedRow()
    lines = text.splitlines()
    lyrics_buffer: list[str] = []
    in_lyrics = False

    for line in lines:
        # LYRICS 블록 안에 있을 때 — 다른 필드 매칭이 나오면 종료
        if in_lyrics:
            # title/tags/persona_id 새로 감지되면 LYRICS 종료
            stripped = line.strip()
            other_field_hit = False
            for fname, pat in _FIELD_PATTERNS.items():
                if fname == "lyrics":
                    continue
                m = pat.match(stripped)
                if m:
                    other_field_hit = True
                    val = _clean_value(m.group(1))
                    if fname == "title" and not parsed.title:
                        parsed.title = val
                    elif fname == "tags" and not parsed.tags:
                        parsed.tags = val
                    elif fname == "persona_id" and not parsed.persona_id:
                        parsed.persona_id = val
                    break
            if other_field_hit:
                in_lyrics = False
                continue
            lyrics_buffer.append(line)
            continue

        # in_lyrics 아닐 때
        stripped = line.strip()
        # LYRICS 라인 시작?
        if _FIELD_PATTERNS["lyrics"].match(stripped):
            in_lyrics = True
            continue
        # title/tags/persona_id 매칭
        for fname in ("title", "tags", "persona_id"):
            m = _FIELD_PATTERNS[fname].match(stripped)
            if m:
                val = _clean_value(m.group(1))
                if fname == "title" and not parsed.title:
                    parsed.title = val
                elif fname == "tags" and not parsed.tags:
                    parsed.tags = val
                elif fname == "persona_id" and not parsed.persona_id:
                    parsed.persona_id = val
                break

    if lyrics_buffer:
        # 앞뒤 빈 줄 제거
        while lyrics_buffer and not lyrics_buffer[0].strip():
            lyrics_buffer.pop(0)
        while lyrics_buffer and not lyrics_buffer[-1].strip():
            lyrics_buffer.pop()
        parsed.lyrics = "\n".join(lyrics_buffer)

    return parsed
