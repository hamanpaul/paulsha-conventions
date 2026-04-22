from __future__ import annotations

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register


@register
class R01ReadmeExists:
    rule_id = "R-01"
    exempt_label = None

    def check(self, ctx: RuleContext) -> RuleResult:
        readme = ctx.repo_root / "README.md"
        if not readme.is_file():
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message="Missing README.md at repository root.",
            )

        size = readme.stat().st_size
        if size < 100:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message=f"README.md is too short ({size} bytes, need >= 100 bytes).",
            )

        return RuleResult(
            rule_id=self.rule_id,
            status=Status.PASS,
            message="README.md exists and satisfies minimum length.",
        )
