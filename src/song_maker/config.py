"""설정 관리. TOML 로드/저장, API 키 제공, 환경변수 오버라이드."""

import os
import tomllib
from pathlib import Path

import tomli_w

CONFIG_DIR = Path.home() / ".songmaker"
CONFIG_PATH = CONFIG_DIR / "config.toml"

DEFAULT_CONFIG = {
    "youtube": {
        "api_key": "",
        "client_id": "",
        "client_secret": "",
        "default_region": "KR",
    },
    "suno": {
        "api_url": "http://localhost:3000",
        "cookie": "",
        "twocaptcha_key": "",
        "provider": "local",
    },
    "gemini": {
        "api_key": "",
        # 이미지 생성 모델 (2026-05 ListModels 기준 실제 사용 가능)
        "model": "gemini-2.5-flash-image",
        "fallback_model": "gemini-3.1-flash-image-preview",
        # 텍스트 생성 모델 (번역기, 가사 변환 등). 안정성 우선 = 2.5-flash
        # preview 모델은 503 UNAVAILABLE 빈도 높아 fallback 우선순위
        "text_model": "gemini-2.5-flash",
        "text_fallback_model": "gemini-3-flash-preview",
    },
    "render": {
        "resolution": "1920x1080",
        "default_fade": 2,
        "subtitle_font": "",
    },
    "upload": {
        "default_privacy": "private",
    },
    "sheets": {
        # Service Account JSON 파일 경로 (~ 확장 지원)
        "service_account_path": "~/.songmaker/service_account.json",
        # 기본 시트 ID (--sheet 옵션으로 덮어쓰기 가능)
        "default_sheet_id": "",
        # 워크시트 이름 (빈 값이면 첫 번째 시트)
        "worksheet": "",
    },
    "capcut": {
        # CapCut에 import할 파일 출력 폴더
        "inbox_dir": "~/CapCut/inbox",
        # CapCut export mp4 받을 폴더
        "outbox_dir": "~/CapCut/outbox",
    },
    "drive": {
        # 부모 폴더 ID (Drive에서 SongMaker 폴더 만들고 SA에게 편집자 공유 후 ID 입력)
        "lyrics_parent_folder_id": "",
        # 활성화 (false면 archive 호출 자체를 안 함)
        "archive_enabled": False,
    },
    "output": {
        # songmaker가 mp3/이미지 등 작업 결과물을 저장할 루트 폴더
        # 빈 값이면 현재 작업 디렉토리의 ./output (cron 실행 시 $HOME/output 됨)
        # 권장: "~/.songmaker/output" 같이 절대경로로 고정
        "dir": "",
    },
}

# 환경변수 → config 매핑
ENV_MAP = {
    "SONGMAKER_YOUTUBE_API_KEY": ("youtube", "api_key"),
    "SONGMAKER_YOUTUBE_CLIENT_ID": ("youtube", "client_id"),
    "SONGMAKER_YOUTUBE_CLIENT_SECRET": ("youtube", "client_secret"),
    "SONGMAKER_YOUTUBE_REGION": ("youtube", "default_region"),
    "SONGMAKER_GEMINI_API_KEY": ("gemini", "api_key"),
    "SONGMAKER_GEMINI_MODEL": ("gemini", "model"),
    "SONGMAKER_SUNO_API_URL": ("suno", "api_url"),
    "SONGMAKER_SUNO_COOKIE": ("suno", "cookie"),
    "SONGMAKER_TWOCAPTCHA_KEY": ("suno", "twocaptcha_key"),
    "SONGMAKER_SUNO_PROVIDER": ("suno", "provider"),
    "SONGMAKER_SHEETS_SA_PATH": ("sheets", "service_account_path"),
    "SONGMAKER_SHEETS_ID": ("sheets", "default_sheet_id"),
}


def _deep_merge(base: dict, override: dict) -> dict:
    """base 딕셔너리에 override를 깊은 병합."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config() -> dict:
    """config.toml 로드 + 환경변수 오버라이드. 파일 없으면 기본값 생��."""
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)

    with open(CONFIG_PATH, "rb") as f:
        config = tomllib.load(f)

    config = _deep_merge(DEFAULT_CONFIG, config)

    # 환경변수 오버라이드 (공백만 있는 값은 무시)
    for env_var, (section, key) in ENV_MAP.items():
        value = os.environ.get(env_var)
        if value and value.strip():
            config.setdefault(section, {})[key] = value

    return config


def save_config(config: dict) -> None:
    """config.toml 저장. API 키 포함이라 소유자 전용 권한으로 저장."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "wb") as f:
        tomli_w.dump(config, f)
    try:
        CONFIG_PATH.chmod(0o600)
    except OSError:
        pass


def get(config: dict, section: str, key: str, default: str = "") -> str:
    """config에서 값 조회."""
    return config.get(section, {}).get(key, default)


def mask_key(value: str) -> str:
    """API 키를 마스킹하여 표시. 'AIza...xxxx' 형태."""
    if not value or len(value) < 8:
        return "(미설정)" if not value else "****"
    return f"{value[:4]}...{value[-4:]}"
