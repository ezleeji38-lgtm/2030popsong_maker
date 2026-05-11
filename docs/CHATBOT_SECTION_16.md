# 챗봇 지침서 Section 16 — songmaker append-row 호환 출력 양식

본인의 ChatGPT 챗봇 system prompt 끝에 **이 섹션 통째로 추가**하면, 챗봇 출력을 그대로 `songmaker append-row`에 넘길 수 있어 시트 입력이 자동화됨.

---

## 추가할 텍스트 (복사 시작)

```
## 16. 시트 입력 자동화 포맷 (songmaker append-row 호환)

가사 생성 완료 후, **마지막 메시지에 정확히 다음 양식으로 한 번 더 출력**한다:

TITLE: <영문 제목 한 줄>
TAGS: <BPM>, <Style>, <Vocal>, <Mood>, <기타 키워드>
LYRICS:
<섹션 마커 포함 가사 전문>

규칙:
1. TITLE/TAGS/LYRICS는 콜론 ":" 직후 한 칸 띄우고 값 입력
2. TAGS는 한 줄, 콤마로 구분 — 예: "95 BPM, Modern Pop, Female vocal, nostalgic"
3. LYRICS는 콜론 직후 줄바꿈, 그 다음부터 가사 시작
4. 가사 안의 섹션 마커는 [Verse 1], [Chorus] 등 그대로 유지
5. 마크다운 강조(**, ##), 이모지 prefix는 사용 가능 (자동 제거됨)

선택 항목:
- PERSONA_ID: <Suno persona UUID>  (보컬 일관성 유지가 필요할 때만)

예시:

TITLE: Midnight Replay
TAGS: 95 BPM, Modern Pop, Female vocal, nostalgic, late night messages
LYRICS:
[Intro]
Late night, on read, again

[Verse 1]
Three dots and they vanish
Same routine, you spell it out

[Pre-Chorus]
Tell me why I do this to me

[Chorus]
You're a midnight replay
Looping in my head all day

(... 나머지 ...)

[Outro]
Late night, on read, again
```

---

## 추가 후 워크플로우

1. 챗봇과 대화하여 가사 완성 (감정 선택 → BPM → 보컬 → 스타일 → ... → 가사)
2. 챗봇 마지막 응답에서 위 양식 블록 통째로 복사
3. 텍스트 파일로 저장: `output_001.txt` (또는 클립보드 그대로)
4. 터미널에서:
   ```bash
   songmaker append-row output_001.txt
   # 또는 클립보드에서 직접:
   pbpaste | songmaker append-row -
   ```
5. 자동으로:
   - TITLE/TAGS/LYRICS 파싱
   - lint 검사 (빈 가사, 너무 김, 마커만 등 차단)
   - 중복 검사 (75% 이상 차단)
   - 통과 시 시트에 `status=pending` 한 행 추가

10곡 모이면:
```bash
songmaker batch
```

## 마크다운/이모지 허용 예시 (모두 정상 파싱됨)

```
## 🎵 TITLE: Cold Coffee
**TAGS:** 100 BPM, R&B Pop, Male vocal, melancholic
🎵 LYRICS:
[Verse 1]
...
```

또는 한국어 콜론도 가능:
```
TITLE：Late Reply
TAGS：90 BPM, Soft Pop, Female vocal, dreamy
LYRICS：
[Verse 1]
...
```
