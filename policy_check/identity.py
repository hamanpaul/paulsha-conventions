"""Distribution identity：這份被安裝的引擎的發行身分（執行期唯讀）。

身分屬於「被安裝的引擎」，不屬於「被檢查的 repo」，因此只從套件資料檔讀取，
不讀環境變數、不讀被檢查 repo 的任何檔案。缺漏或不合法一律 fail-closed，
不得回退到硬編碼預設值（回退等同悄悄放寬信任）。
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Any

import yaml

REQUIRED_FIELDS = (
    "canonical_org",
    "engine_repo",
    "remote_base",
    "distribution_name",
    "provider",
)
VALID_PROVIDERS = {"github", "gitlab"}


class IdentityError(RuntimeError):
    """Distribution identity 缺漏或不合法。"""


@dataclass(frozen=True)
class DistributionIdentity:
    canonical_org: str
    engine_repo: str
    remote_base: str
    distribution_name: str
    provider: str
    # 選填：發行編號。只進 manifest 與報告，不進 artifact 檔名
    # （integrity.py:23 的目錄名正則內嵌版號語法，階段一不得更動）。
    distribution_build: int | None = None

    def remote_urls(self) -> set[str]:
        base = self.remote_base.rstrip("/")
        host = base.split("://", 1)[-1]
        return {
            f"{base}/{self.engine_repo}",
            f"ssh://git@{host}/{self.engine_repo}",
            f"git@{host}:{self.engine_repo}",
        }


def _load_raw() -> dict[str, Any]:
    try:
        raw = files("policy_check.data").joinpath("distribution.yml").read_text(
            encoding="utf-8"
        )
    except (OSError, UnicodeError) as exc:
        raise IdentityError(f"cannot read distribution.yml: {exc}") from exc
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise IdentityError(f"distribution.yml is not valid YAML: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise IdentityError(
            "distribution.yml must be a mapping at the top level, got "
            f"{type(data).__name__}"
        )
    return data


@lru_cache(maxsize=1)
def identity() -> DistributionIdentity:
    data = _load_raw()
    missing = [f for f in REQUIRED_FIELDS if not str(data.get(f) or "").strip()]
    if missing:
        raise IdentityError(
            f"distribution identity incomplete: {', '.join(missing)}"
        )
    provider = str(data["provider"]).strip()
    if provider not in VALID_PROVIDERS:
        raise IdentityError(
            "distribution identity provider must be one of "
            f"{sorted(VALID_PROVIDERS)}, got {provider!r}"
        )
    build = data.get("distribution_build")
    if build is not None:
        try:
            build = int(build)
        except (TypeError, ValueError):
            raise IdentityError(
                f"distribution_build must be an integer, got {build!r}"
            ) from None
    return DistributionIdentity(
        canonical_org=str(data["canonical_org"]).strip(),
        engine_repo=str(data["engine_repo"]).strip(),
        remote_base=str(data["remote_base"]).strip(),
        distribution_name=str(data["distribution_name"]).strip(),
        provider=provider,
        distribution_build=build,
    )
