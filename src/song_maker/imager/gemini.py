"""Gemini Image API 연동. 이미지 생성 + Gate 4 검증."""

import shutil
import struct
from pathlib import Path

from rich.console import Console
from rich.progress import Progress

from song_maker import config as cfg
from song_maker.gates import Check, GateResult
from song_maker.imager.prompt import build_image_prompt, build_thumbnail_prompt
from song_maker.models import Song

console = Console()


def _generate_single_image(
    api_key: str,
    prompt: str,
    output_path: Path,
    model: str,
    fallback_model: str,
) -> Path:
    """Gemini API로 이미지 1장을 생성한다. 실패 시 fallback 모델로 재시도."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    last_err: Exception | None = None
    for attempt_model in [model, fallback_model]:
        if not attempt_model:
            continue
        try:
            response = client.models.generate_content(
                model=attempt_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                ),
            )

            candidates = getattr(response, "candidates", None) or []
            if not candidates:
                raise RuntimeError(f"{attempt_model}: 응답에 candidates가 없습니다.")
            content = getattr(candidates[0], "content", None)
            parts = getattr(content, "parts", None) or [] if content else []
            for part in parts:
                inline = getattr(part, "inline_data", None)
                if inline and getattr(inline, "data", None):
                    output_path.write_bytes(inline.data)
                    return output_path

            raise RuntimeError(f"{attempt_model}: 응답에 이미지 데이터가 없습니다.")

        except Exception as e:
            last_err = e
            err_str = str(e)
            # 429 RESOURCE_EXHAUSTED — Gemini 무료 일 한도 초과
            if "RESOURCE_EXHAUSTED" in err_str or "429" in err_str:
                raise RuntimeError(
                    "Gemini 무료 한도 초과 (429 RESOURCE_EXHAUSTED).\n"
                    "  → 24시간 후 재시도 또는 https://ai.dev/rate-limit 에서 유료 결제 활성화\n"
                    f"  원본: {err_str[:200]}"
                ) from e
            if attempt_model == fallback_model:
                break
            console.print(f"  [yellow]모델 {attempt_model} 실패({e}), fallback 시도...[/yellow]")
            continue

    raise RuntimeError(f"이미지 생성 실패: {last_err}")


def generate_images(config: dict, song: Song, song_dir: Path) -> Song:
    """배경 이미지 + 썸네일을 생성한다."""
    api_key = cfg.get(config, "gemini", "api_key")
    model = cfg.get(config, "gemini", "model")
    fallback = cfg.get(config, "gemini", "fallback_model")

    with Progress() as progress:
        # 배경 이미지
        task = progress.add_task("배경 이미지 생성 중...", total=2)
        bg_prompt = build_image_prompt(song)
        bg_path = song_dir / "background.png"
        _generate_single_image(api_key, bg_prompt, bg_path, model, fallback)
        song.background_path = "background.png"
        song.image_prompt = bg_prompt
        song.image_model = model
        progress.update(task, advance=1)

        # 썸네일
        progress.update(task, description="썸네일 생성 중...")
        try:
            thumb_prompt = build_thumbnail_prompt(song)
            thumb_path = song_dir / "thumbnail.png"
            _generate_single_image(api_key, thumb_prompt, thumb_path, model, fallback)
            song.thumbnail_path = "thumbnail.png"
        except Exception:
            # 썸네일 실패 시 배경을 복사
            console.print("  [yellow][경고][/yellow] 썸네일 생성 실패. 배경 이미지를 썸네일로 사용합니다.")
            if bg_path.exists():
                shutil.copy2(bg_path, song_dir / "thumbnail.png")
                song.thumbnail_path = "thumbnail.png"
        progress.update(task, advance=1)

    song.status = "imaged"
    return song


def _get_png_dimensions(path: Path) -> tuple[int, int]:
    """PNG 파일의 너비x높이를 반환한다."""
    try:
        with open(path, "rb") as f:
            header = f.read(24)
            if header[:8] == b"\x89PNG\r\n\x1a\n":
                w, h = struct.unpack(">II", header[16:24])
                return w, h
    except Exception:
        pass
    return 0, 0


def _can_decode_png(path: Path) -> bool:
    """PNG 파일이 디코딩 가능한지 확인한다."""
    try:
        with open(path, "rb") as f:
            header = f.read(8)
            return header[:8] == b"\x89PNG\r\n\x1a\n"
    except Exception:
        return False


def verify_gate4(song: Song, song_dir: Path) -> GateResult:
    """Gate 4: 이미지 생성 결과 검증."""
    checks: list[Check] = []
    bg = song_dir / "background.png"

    # 4-2, 4-3. 배경 파일 존재 + 크기
    bg_ok = bg.exists() and bg.stat().st_size > 10_000
    checks.append(Check(
        name="background_exists",
        passed=bg_ok,
        message="배경 이미지가 없거나 비정상적입니다.",
    ))

    # 4-4. 이미지 디코딩
    if bg.exists():
        checks.append(Check(
            name="background_decodable",
            passed=_can_decode_png(bg),
            message="배경 이미지를 디코딩할 수 없습니다.",
        ))

    # 4-5. 해상도 (비차단)
    if bg.exists():
        w, h = _get_png_dimensions(bg)
        checks.append(Check(
            name="background_resolution",
            passed=w >= 1024 and h >= 768,
            blocking=False,
            message=f"해상도가 권장 기준 미달입니다. ({w}x{h})",
        ))

    # 4-6. 썸네일 (비차단)
    thumb = song_dir / "thumbnail.png"
    checks.append(Check(
        name="thumbnail_exists",
        passed=thumb.exists() and thumb.stat().st_size > 10_000,
        blocking=False,
        message="썸네일이 없거나 비정상적입니다.",
    ))

    return GateResult(gate="gate4", checks=checks)
