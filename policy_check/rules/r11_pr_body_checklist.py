from __future__ import annotations

import re

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register


@register
class R11PrBodyChecklist:
    rule_id = "R-11"
    exempt_label = "wip"

    _unchecked_checkbox_pattern = re.compile(r"(?mi)^\s*[-*]\s+\[\s\]\s*.*$")

    def check(self, ctx: RuleContext) -> RuleResult:
        if self.exempt_label in ctx.pr_labels:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.SKIP,
                message="R-11 skipped for wip PR.",
                exempt_label=self.exempt_label,
            )

        if not ctx.pr_body:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message="No PR body provided; treat as non-PR context.",
            )

        unchecked = self._unchecked_checkbox_pattern.findall(ctx.pr_body)
        if unchecked:
            preview = "\n".join(line.strip() for line in unchecked[:5])
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message=f"PR body contains unchecked checklist items: {len(unchecked)}.",
                detail=preview,
            )

        return RuleResult(
            rule_id=self.rule_id,
            status=Status.PASS,
            message="PR body checklist is fully checked.",
        )
