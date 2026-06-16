from __future__ import annotations

import re
import subprocess
from fnmatch import fnmatch
from pathlib import Path

from policy_check.rules._secret_scan_config import resolve_markers
from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register

# 結構偵測器（恆開，寫死在 code）：個人絕對路徑、私鑰
_STRUCTURAL = re.compile(r"/home/[a-z_][a-z0-9_-]*/")
_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")


def _build_marker_re(tokens: set[str]) -> re.Pattern[str] | None:
    """由 config-driven 的 marker tokens 組成單一不分大小寫的字界 regex。"""
    if not tokens:
        return None
    alt = "|".join(re.escape(t) for t in sorted(tokens))
    return re.compile(rf"\b({alt})\b", re.IGNORECASE)

_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv"}
_BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip",
               ".gz", ".bin", ".ico", ".woff", ".woff2"}

_SELF_EXEMPT = (
    "policy_check/rules/r21_secret_scan.py",
    "policy_check/rules/_secret_scan_config.py",
    "policy_check/data/secret_scan_defaults.yml",
    "tests/test_rule_r21_secret_scan.py",
    "tests/test_secret_scan_config.py",
    "tests/fixtures/secret-scan/**",
)


def _is_exempt(rel: str, allow: list[str]) -> bool:
    for pat in (*_SELF_EXEMPT, *allow):
        if fnmatch(rel, pat):
            return True
        base = pat[:-2] if pat.endswith("/**") else pat
        if rel == base or rel.startswith(base.rstrip("/") + "/"):
            return True
    return False


def _git_tracked_files(root: Path) -> list[str] | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    if not result.stdout:
        return None
    return [f for f in result.stdout.split("\0") if f]


def _iter_text_files(root: Path):
    tracked = _git_tracked_files(root)
    if tracked is not None:
        candidates = (root / rel for rel in tracked)
    else:
        candidates = (p for p in root.rglob("*"))
    for p in candidates:
        if not p.is_file():
            continue
        rel_parts = p.relative_to(root).parts
        if any(part in _SKIP_DIRS for part in rel_parts):
            continue
        if p.suffix.lower() in _BINARY_EXT:
            continue
        yield p


@register
class R21SecretScan:
    rule_id = "R-21"
    exempt_label = "policy-exempt:secret-scan"

    def check(self, ctx: RuleContext) -> RuleResult:
        if self.exempt_label in ctx.pr_labels:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.SKIP,
                message=f"Skipped by exemption label: {self.exempt_label}.",
                exempt_label=self.exempt_label,
            )

        tier = (ctx.config or {}).get("tier")
        if tier != "shareable":
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message=(
                    f"tier={tier!r}; R-21 enforces only tier=shareable. "
                    "Not applicable."
                ),
            )

        config = ctx.config or {}
        allow = (config.get("secret_scan") or {}).get("allow", [])
        marker_re = _build_marker_re(resolve_markers(config))
        hits: list[str] = []
        for path in _iter_text_files(ctx.repo_root):
            rel = path.relative_to(ctx.repo_root).as_posix()
            if _is_exempt(rel, allow):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for ln, line in enumerate(text.splitlines(), 1):
                if _STRUCTURAL.search(line) or _PRIVATE_KEY.search(line) or (
                    marker_re is not None and marker_re.search(line)
                ):
                    hits.append(f"{rel}:{ln}")
                    break
        if hits:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message=f"shareable repo contains confidential markers in {len(hits)} file(s).",
                detail="\n".join(hits[:20]),
            )
        return RuleResult(
            rule_id=self.rule_id,
            status=Status.PASS,
            message="No confidential markers detected.",
        )
