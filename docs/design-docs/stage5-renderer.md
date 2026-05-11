# Stage 5 — FFmpeg 렌더링 상세 설계

## 1. 목적

생성된 오디오(MP3)와 배경 이미지(PNG)를 합쳐 유튜브 업로드용 MP4 영상을 렌더링한다. 선택적으로 가사 자막과 효과를 추가한다.

---

## 2. 모듈 구성

```
renderer/
├── __init__.py
└── ffmpeg.py       # FFmpeg 명령어 조합 + 실행
```

---

## 3. ffmpeg.py 상세

### 사전 조건 체크

```python
def check_ffmpeg() -> bool:
    """FFmpeg 설치 여부 확인"""
    return shutil.which("ffmpeg") is not None

def check_ffprobe() -> bool:
    """ffprobe 설치 여부 확인"""
    return shutil.which("ffprobe") is not None
```

### 기본 렌더링

```python
def render(
    audio: Path,
    background: Path,
    output: Path,
    resolution: str = "1920x1080",
    fade_duration: float = 0,
    subtitles: Path | None = None
) -> Path:
```

**기본 FFmpeg 명령어:**
```bash
ffmpeg -y \
  -loop 1 -i background.png \
  -i audio.mp3 \
  -c:v libx264 -tune stillimage \
  -c:a aac -b:a 192k \
  -pix_fmt yuv420p \
  -s 1920x1080 \
  -shortest \
  output.mp4
```

### 옵션별 명령어 확장

**페이드 효과 추가 시:**
```bash
-vf "fade=t=in:st=0:d={fade},fade=t=out:st={duration-fade}:d={fade}"
-af "afade=t=in:st=0:d={fade},afade=t=out:st={duration-fade}:d={fade}"
```

**가사 자막 추가 시:**
```bash
# 폰트는 config.toml [render].subtitle_font 에서 설정 (기본: 시스템 폰트)
-vf "subtitles=lyrics.srt:force_style='FontSize=28,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2,Alignment=2,MarginV=50'"
```

> **폰트 참고**: `FontName`을 지정하지 않으면 FFmpeg가 시스템 기본 폰트를 사용한다.
> 한글 자막이 깨지면 config.toml에서 폰트를 지정한다:
> ```toml
> [render]
> subtitle_font = "Malgun Gothic"   # Windows 기본 한글 폰트
> # subtitle_font = "AppleGothic"   # macOS
> # subtitle_font = "NanumGothic"   # Linux (설치 필요)
> ```

### 오디오 길이 측정

```python
def get_audio_duration(audio_path: Path) -> float:
    """ffprobe로 오디오 길이(초) 반환"""
    result = subprocess.run([
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        str(audio_path)
    ], capture_output=True, text=True)
    return float(result.stdout.strip())
```

### 가사 → SRT 변환

가사 파일을 SRT 자막 형식으로 변환:

```python
def lyrics_to_srt(lyrics_path: Path, duration: float) -> Path:
    """
    lyrics.txt를 lyrics.srt로 변환
    각 줄을 균등 분배하여 타임코드 할당
    """
    lines = lyrics_path.read_text(encoding="utf-8").strip().split("\n")
    interval = duration / len(lines)

    srt_content = ""
    for i, line in enumerate(lines):
        start = format_srt_time(i * interval)
        end = format_srt_time((i + 1) * interval)
        srt_content += f"{i+1}\n{start} --> {end}\n{line}\n\n"

    srt_path = lyrics_path.with_suffix(".srt")
    srt_path.write_text(srt_content, encoding="utf-8")
    return srt_path
```

### 명령어 조합

```python
def build_ffmpeg_command(
    audio: Path, background: Path, output: Path,
    resolution: str, fade: float, subtitles: Path | None
) -> list[str]:
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(background),
        "-i", str(audio),
        "-c:v", "libx264", "-tune", "stillimage",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-s", resolution,
    ]

    vf_filters = []
    if subtitles:
        font = config.get("render", {}).get("subtitle_font", "")
        style = f"FontName={font}," if font else ""
        vf_filters.append(f"subtitles={subtitles}:force_style='{style}FontSize=28'")
    if fade > 0:
        duration = get_audio_duration(audio)
        vf_filters.append(f"fade=t=in:st=0:d={fade}")
        vf_filters.append(f"fade=t=out:st={duration-fade}:d={fade}")

    if vf_filters:
        cmd.extend(["-vf", ",".join(vf_filters)])

    cmd.extend(["-shortest", str(output)])
    return cmd
```

### 실행 + 에러 처리

```python
def run_ffmpeg(cmd: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout
    )

    if result.returncode != 0:
        raise RenderError(
            f"FFmpeg 에러 (exit code {result.returncode}):\n"
            f"{result.stderr[-500:]}"  # 마지막 500자만
        )

    return result
```

---

## 4. 렌더링 진행 표시

FFmpeg의 progress를 파싱하여 진행바 표시:

```python
# -progress pipe:1 옵션으로 진행 상황 수신
# out_time_ms를 파싱하여 진행률 계산
progress = out_time_ms / (duration * 1_000_000) * 100
```

```
영상 렌더링 중... ━━━━━━━━━━━━━━━━━━━━ 67% 0:02:15
```

---

## 5. 저장 구조

```
output/{project_name}/{song_id}/
├── meta.json
├── audio.mp3
├── lyrics.txt
├── lyrics.srt          ← 자막 (자막 옵션 시)
├── background.png
├── thumbnail.png
└── video.mp4           ← 렌더링 결과
```

meta.json 업데이트:
```json
{
  "status": "rendered",
  "video_path": "video.mp4",
  "render_options": {
    "resolution": "1920x1080",
    "fade": 2,
    "subtitles": true
  }
}
```

---

## 6. Gate 5 검증 연계

이 Stage 완료 후 Gate 5가 실행된다:
- FFmpeg 종료 코드 == 0
- video.mp4 존재
- 파일 크기 1MB ~ 500MB
- 비디오 스트림 H.264 감지
- 오디오 스트림 AAC 감지
- 영상 길이 ≈ 오디오 길이 (비차단)
- 해상도 일치 (비차단)

Gate 5 통과 시 → Stage 6 (업로드)로 진행.
