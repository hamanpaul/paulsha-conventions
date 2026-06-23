from __future__ import annotations

import re

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.r13_agent_files_exist import AGENT_FILES
from policy_check.rules.registry import register

VER_RE = re.compile(r"^policy_version:\s*([0-9]+\.[0-9]+\.[0-9]+(?:-fix\.\d+)?)\s*$", re.MULTILINE)

CANONICAL = "CLAUDE.md"


@register
class R14AgentFilesVersion:
    rule_id = "R-14"
    exempt_label = None

    def check(self, ctx: RuleContext) -> RuleResult:
        agent_files_cfg = ctx.config.get("agent_files") or {}
        mode = agent_files_cfg.get("mode", "copy") if isinstance(agent_files_cfg, dict) else "copy"
        if mode == "symlink":
            return self._check_symlink(ctx)
        return self._check_copy(ctx)

    def _check_copy(self, ctx: RuleContext) -> RuleResult:
        declared = ctx.policy_version
        mismatches: list[str] = []
        for name in AGENT_FILES:
            path = ctx.repo_root / name
            if not path.is_file():
                continue  # R-13 handles missing required agent files.
            text = path.read_text(encoding="utf-8", errors="replace")
            match = VER_RE.search(text)
            if not match:
                mismatches.append(f"{name}: policy_version not declared")
                continue
            found = match.group(1)
            if found != declared:
                mismatches.append(f"{name}: policy_version {found} != declared {declared}")
        if mismatches:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message="agent file version drift",
                detail="\n".join(mismatches),
            )
        return RuleResult(
            rule_id=self.rule_id,
            status=Status.PASS,
            message=f"agent files aligned to policy_version {declared}",
        )

    def _check_symlink(self, ctx: RuleContext) -> RuleResult:
        declared = ctx.policy_version
        problems: list[str] = []
        canonical_path = ctx.repo_root / CANONICAL

        if canonical_path.is_symlink():
            problems.append(f"{CANONICAL}: canonical must be a regular file, found symlink")
        elif canonical_path.is_file():
            text = canonical_path.read_text(encoding="utf-8", errors="replace")
            match = VER_RE.search(text)
            if not match:
                problems.append(f"{CANONICAL}: policy_version not declared")
            elif match.group(1) != declared:
                problems.append(f"{CANONICAL}: policy_version {match.group(1)} != declared {declared}")
        # 缺 canonical 交由 R-13

        canonical_resolved = canonical_path.resolve()
        for name in AGENT_FILES:
            if name == CANONICAL:
                continue
            path = ctx.repo_root / name
            if not path.exists():
                continue  # 缺檔／斷鏈交由 R-13
            if not path.is_symlink():
                problems.append(f"{name}: expected symlink → {CANONICAL}, found regular file")
                continue
            if path.resolve() != canonical_resolved:
                problems.append(f"{name}: symlink target mismatch (expected {CANONICAL})")

        if problems:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message="agent file single-source integrity violation",
                detail="\n".join(problems),
            )
        return RuleResult(
            rule_id=self.rule_id,
            status=Status.PASS,
            message=f"agent files single-source (symlink → {CANONICAL}) aligned to {declared}",
        )
