from __future__ import annotations

import re

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register


@register
class R10PrTitle:
    rule_id = "R-10"
    exempt_label = "policy-exempt:pr-title"

    _conventional_title_pattern = re.compile(
        r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)"
        r"(\([a-z0-9][a-z0-9._/-]*\))?"
        r"!?"
        r":\s+\S.+$"
    )

    def check(self, ctx: RuleContext) -> RuleResult:
        if self.exempt_label in ctx.pr_labels:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.SKIP,
                message=f"R-10 exempted by label: {self.exempt_label}",
                exempt_label=self.exempt_label,
            )

        if not ctx.pr_title:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message="No PR title provided; treat as non-PR context.",
            )

        title = ctx.pr_title.strip()
        if self._conventional_title_pattern.match(title):
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message="PR title matches conventional commit format.",
            )

        return RuleResult(
            rule_id=self.rule_id,
            status=Status.FAIL,
            message="PR title must follow conventional commit format.",
            detail=(
                "expected: type(scope)?: subject, for example 'feat(parser): add support'"
            ),
        )
