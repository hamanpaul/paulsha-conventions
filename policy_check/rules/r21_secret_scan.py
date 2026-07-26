from __future__ import annotations

import re
import subprocess
from fnmatch import fnmatch
from pathlib import Path

from policy_check.rules._secret_scan_config import resolve_markers
from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register

# 結構偵測器（恆開，寫死在 code）：個人絕對路徑、私鑰
# IGNORECASE 還原原 _EMPLOYER_MARKERS 行為：大寫 username（/home/Paul/）與 /HOME/ 也須命中
_STRUCTURAL = re.compile(r"/home/[a-z_][a-z0-9_-]*/", re.IGNORECASE)
_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
_AWS_ACCESS_KEY = re.compile(r"\b(?:AKIA|ASIA|A3T|AIDA|AGPA)[A-Z0-9]{16}\b")
_GITHUB_TOKEN = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")


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


def _normalize_visibility(value) -> str:
    if not isinstance(value, str):
        return "unknown"
    v = value.strip().lower()
    if v in {"public", "private", "internal", "unknown"}:
        return v
    return "unknown"


def _visibility_status(visibility: str, detector: str) -> Status:
    if detector in {"structural", "credential"}:
        if visibility in {"public", "unknown"}:
            return Status.FAIL
        return Status.WARN
    if visibility in {"public", "private", "internal", "unknown"}:
        return Status.WARN
    return Status.FAIL


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
        config = ctx.config or {}
        allow = (config.get("secret_scan") or {}).get("allow", [])
        marker_re = _build_marker_re(resolve_markers(config))
        visibility = _normalize_visibility(ctx.repo_visibility)
        hit_records: list[tuple[str, int, str]] = []
        hit_counts: dict[str, int] = {"structural": 0, "credential": 0, "marker": 0}

        def record_hit(rel: str, line_number: int, detector: str) -> None:
            hit_counts[detector] += 1
            if len(hit_records) < 20:
                hit_records.append((rel, line_number, detector))

        for path in _iter_text_files(ctx.repo_root):
            rel = path.relative_to(ctx.repo_root).as_posix()
            if _is_exempt(rel, allow):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for ln, line in enumerate(text.splitlines(), 1):
                if _STRUCTURAL.search(line) or _PRIVATE_KEY.search(line):
                    record_hit(rel, ln, "structural")
                if _AWS_ACCESS_KEY.search(line) or _GITHUB_TOKEN.search(line):
                    record_hit(rel, ln, "credential")
                if marker_re is not None and marker_re.search(line):
                    record_hit(rel, ln, "marker")
        if any(hit_counts.values()):
            rank = {Status.PASS: 0, Status.WARN: 1, Status.FAIL: 2}
            final_status = Status.PASS
            if tier == "shareable":
                final_status = Status.FAIL
            else:
                for detector in ("structural", "credential", "marker"):
                    if hit_counts[detector] <= 0:
                        continue
                    candidate = _visibility_status(visibility, detector)
                    if rank[candidate] > rank[final_status]:
                        final_status = candidate

            summary = ", ".join(
                f"{k}:{hit_counts[k]}" for k in ("structural", "credential", "marker")
            )
            message = (
                f"R-21 findings with tier={tier!r}, visibility={visibility!r}: {summary}."
            )
            if visibility == "unknown" and tier != "shareable":
                message = (
                    f"{message} visibility is unknown; apply least-privilege coupling."
                )
            return RuleResult(
                rule_id=self.rule_id,
                status=final_status,
                message=message,
                detail="\n".join(f"{r}:{ln} {detector}" for r, ln, detector in hit_records),
            )
        return RuleResult(
            rule_id=self.rule_id,
            status=Status.PASS,
            message=(
                f"No R-21 confidentiality hits under tier={tier!r}, visibility={visibility!r}."
            ),
        )
