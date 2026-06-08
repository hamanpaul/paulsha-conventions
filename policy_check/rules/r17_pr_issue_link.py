from __future__ import annotations

import re

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register


@register
class R17PrIssueLink:
    rule_id = "R-17"
    exempt_label = "policy-exempt:issue-link"

    # Bare issue reference, e.g. "#12". ATX headings ("# Title") never match
    # because a digit must immediately follow the hash.
    _issue_ref_pattern = re.compile(r"#\d+")

    # GitHub-recognized closing keywords + an issue reference, e.g. "Closes #12",
    # "Fixes: #3", "resolved #45". Presence of any one auto-closes the issue and
    # records a cross-reference on the issue timeline when merged into the default branch.
    _closing_pattern = re.compile(
        r"(?i)\b(?:close[sd]?|fix(?:es|ed)?|resolve[sd]?)\b[:\s]+#\d+"
    )

    def check(self, ctx: RuleContext) -> RuleResult:
        if self.exempt_label in ctx.pr_labels:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.SKIP,
                message=f"R-17 exempted by label: {self.exempt_label}",
                exempt_label=self.exempt_label,
            )

        if not ctx.pr_body:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message="No PR body provided; treat as non-PR context.",
            )

        if not self._issue_ref_pattern.search(ctx.pr_body):
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message="No issue reference in PR body; nothing to link.",
            )

        if self._closing_pattern.search(ctx.pr_body):
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message="PR body links an issue with a closing keyword.",
            )

        return RuleResult(
            rule_id=self.rule_id,
            status=Status.FAIL,
            message=(
                "PR body references an issue (#N) but uses no closing keyword. "
                "Use Closes/Fixes/Resolves #N so merge auto-closes and cross-references "
                "the issue, or apply the policy-exempt:issue-link label for reference-only PRs."
            ),
        )
