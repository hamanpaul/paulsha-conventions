from __future__ import annotations

import re

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.r13_agent_files_exist import AGENT_FILES
from policy_check.rules.registry import register

VER_RE = re.compile(r"^policy_version:\s*([0-9]+\.[0-9]+\.[0-9]+(?:-fix\.\d+)?)\s*$", re.MULTILINE)


@register
class R14AgentFilesVersion:
    rule_id = "R-14"
    exempt_label = None

    def check(self, ctx: RuleContext) -> RuleResult:
        declared = ctx.policy_version
        mismatches: list[str] = []

        for name in AGENT_FILES:
            path = ctx.repo_root / name
            if not path.is_file():
                # R-13 handles missing required agent files.
                continue

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
