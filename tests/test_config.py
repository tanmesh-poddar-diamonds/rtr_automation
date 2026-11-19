from pathlib import Path

import pytest

from config import load_config

BASE = "https://h/p.aspx?SID=abc_123&mode=ring_3_d&sub=admin_panel&d=XYZ"


def test_defaults_and_types():
    cfg = load_config({"BASE_URL": BASE})
    assert cfg.base_url == BASE
    assert cfg.output_dir == Path("output")
    assert cfg.log_dir == Path("logs")
    assert cfg.stall_timeout_s == 120
    assert cfg.progress_log_every == 25
    assert cfg.browser_channel == "chrome"
    assert cfg.headless is False
    assert cfg.ring_prefix == "833"


def test_overrides():
    cfg = load_config({"BASE_URL": BASE, "OUTPUT_DIR": "o", "STALL_TIMEOUT_S": "30",
                       "HEADLESS": "true", "RING_PREFIX": "900"})
    assert cfg.output_dir == Path("o")
    assert cfg.stall_timeout_s == 30
    assert cfg.headless is True
    assert cfg.ring_prefix == "900"


def test_missing_base_url_raises():
    with pytest.raises(ValueError, match="BASE_URL"):
        load_config({})


def test_base_url_without_sid_raises():
    with pytest.raises(ValueError, match="SID"):
        load_config({"BASE_URL": "https://h/p.aspx?mode=x"})


def test_ring_id_param_is_stripped_from_base_url():
    cfg = load_config({"BASE_URL": BASE + "&ring_id=833-A-not_resizable_PR-0.00-01.glb"})
    assert cfg.base_url == BASE
