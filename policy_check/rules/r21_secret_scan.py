from __future__ import annotations

import re
from pathlib import Path

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register

_EMPLOYER_MARKERS = re.compile(
    r"\b(brcm|broadcom|airoha|prplos|prplog|bgw720|build20)\b"
    r"|/home/[a-z_][a-z0-9_-]*/",
    re.IGNORECASE,
)
_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")

_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv"}
_BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip",
               ".gz", ".bin", ".ico", ".woff", ".woff2"}


def _iter_text_files(root: Path):
    for p in root.rglob("*"):
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
        hits: list[str] = []
        for path in _iter_text_files(ctx.repo_root):
            rel = path.relative_to(ctx.repo_root).as_posix()
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for ln, line in enumerate(text.splitlines(), 1):
                if _EMPLOYER_MARKERS.search(line) or _PRIVATE_KEY.search(line):
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
