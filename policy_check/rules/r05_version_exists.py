from __future__ import annotations

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register


@register
class R05VersionExists:
    rule_id = "R-05"
    exempt_label = None

    def check(self, ctx: RuleContext) -> RuleResult:
        target = ctx.repo_root / "VERSION"
        if target.is_file():
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message="VERSION exists at repository root.",
            )

        return RuleResult(
            rule_id=self.rule_id,
            status=Status.FAIL,
            message="Missing VERSION at repository root.",
            detail="Checked: VERSION",
        )
