from __future__ import annotations

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register

AGENT_FILES = [
    "CLAUDE.md",
    "AGENTS.md",
    "GEMINI.md",
    ".github/copilot-instructions.md",
]


@register
class R13AgentFilesExist:
    rule_id = "R-13"
    exempt_label = "policy-exempt:agent-files"

    def check(self, ctx: RuleContext) -> RuleResult:
        if self.exempt_label in ctx.pr_labels:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.SKIP,
                message=f"R-13 exempted by label: {self.exempt_label}",
                exempt_label=self.exempt_label,
            )

        missing = [name for name in AGENT_FILES if not (ctx.repo_root / name).is_file()]
        if missing:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message=f"missing agent convention files: {missing}",
            )

        return RuleResult(
            rule_id=self.rule_id,
            status=Status.PASS,
            message="all agent convention files present",
        )
