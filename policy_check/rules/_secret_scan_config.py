"""R-21 機密標記設定：載入 baseline 資料檔並與 repo config 疊加（extend-only）。"""
from __future__ import annotations

from importlib.resources import files
from typing import Any

import yaml


def load_baseline() -> dict[str, list[str]]:
    """從套件資料檔載入 baseline markers / public_names。"""
    raw = files("policy_check.data").joinpath("secret_scan_defaults.yml").read_text(
        encoding="utf-8"
    )
    data = yaml.safe_load(raw) or {}
    return {
        "markers": [str(t).lower() for t in (data.get("markers") or [])],
        "public_names": [str(t).lower() for t in (data.get("public_names") or [])],
    }


def _repo_list(config: dict[str, Any], key: str) -> list[str]:
    sec = (config or {}).get("secret_scan") or {}
    raw = sec.get(key) or []
    return [str(t).lower() for t in raw if str(t).strip()]


def resolve_markers(config: dict[str, Any]) -> set[str]:
    """effective markers = (baseline.markers ∪ repo.markers) − public_names。extend-only。"""
    base = load_baseline()
    markers = set(base["markers"]) | set(_repo_list(config, "markers"))
    public = set(base["public_names"]) | set(_repo_list(config, "public_names"))
    return markers - public
