import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class Config:
    base_url: str
    output_dir: Path
    log_dir: Path
    stall_timeout_s: int
    progress_log_every: int
    browser_channel: str
    headless: bool
    ring_prefix: str


def _bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_config(env: Mapping[str, str] | None = None) -> Config:
    env = os.environ if env is None else env
    base_url = (env.get("BASE_URL") or "").strip()
    if not base_url:
        raise ValueError("BASE_URL is not set (put it in .env, see .env.example)")
    if "SID=" not in base_url:
        raise ValueError("BASE_URL must contain the session id (SID=...)")
    base_url = re.sub(r"&ring_id=[^&]*", "", base_url)
    return Config(
        base_url=base_url,
        output_dir=Path(env.get("OUTPUT_DIR") or "output"),
        log_dir=Path(env.get("LOG_DIR") or "logs"),
        stall_timeout_s=int(env.get("STALL_TIMEOUT_S") or 120),
        progress_log_every=int(env.get("PROGRESS_LOG_EVERY") or 25),
        browser_channel=env.get("BROWSER_CHANNEL") or "chrome",
        headless=_bool(env.get("HEADLESS") or "true"),
        ring_prefix=env.get("RING_PREFIX") or "833",
    )
