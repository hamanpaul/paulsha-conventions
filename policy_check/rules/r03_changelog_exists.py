from __future__ import annotations

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register


@register
class R03ChangelogExists:
    rule_id = "R-03"
    exempt_label = None

    def check(self, ctx: RuleContext) -> RuleResult:
        target = ctx.repo_root / "CHANGELOG.md"
        if target.is_file():
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message="CHANGELOG.md exists at repository root.",
            )

        return RuleResult(
            rule_id=self.rule_id,
            status=Status.FAIL,
            message="Missing CHANGELOG.md at repository root.",
        )
