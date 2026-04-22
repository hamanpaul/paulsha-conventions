from __future__ import annotations

import re

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register


@register
class R12BranchSource:
    rule_id = "R-12"
    exempt_label = "policy-exempt:branch-name"

    _feature_pattern = re.compile(r"^feature/(?P<slug>[a-z0-9][a-z0-9-]*)$")
    _worktree_pattern = re.compile(r"^wt/(?P<slug>[a-z0-9][a-z0-9-]*)/(?P<subtask>[a-z0-9][a-z0-9-]*)$")

    def check(self, ctx: RuleContext) -> RuleResult:
        if self.exempt_label in ctx.pr_labels:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.SKIP,
                message=f"R-12 exempted by label: {self.exempt_label}",
                exempt_label=self.exempt_label,
            )

        if not ctx.pr_base_ref or not ctx.pr_head_ref:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message="Missing PR base/head ref; treat as non-PR context.",
            )

        base = ctx.pr_base_ref.strip()
        head = ctx.pr_head_ref.strip()

        if base == "main":
            if self._feature_pattern.match(head):
                return RuleResult(
                    rule_id=self.rule_id,
                    status=Status.PASS,
                    message="Branch naming is valid for PR into main.",
                )
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message="When base is main, head must be feature/<slug>.",
            )

        feature_base = self._feature_pattern.match(base)
        if feature_base:
            expected_slug = feature_base.group("slug")
            worktree_head = self._worktree_pattern.match(head)
            if not worktree_head:
                return RuleResult(
                    rule_id=self.rule_id,
                    status=Status.FAIL,
                    message=(
                        f"When base is feature/{expected_slug}, "
                        f"head must be wt/{expected_slug}/<subtask>."
                    ),
                )

            head_slug = worktree_head.group("slug")
            if head_slug != expected_slug:
                return RuleResult(
                    rule_id=self.rule_id,
                    status=Status.FAIL,
                    message=(
                        f"When base is feature/{expected_slug}, "
                        f"head must be wt/{expected_slug}/<subtask>."
                    ),
                )

            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message="Branch naming is valid for worktree PR into feature branch.",
            )

        return RuleResult(
            rule_id=self.rule_id,
            status=Status.PASS,
            message="Base branch is outside R-12 scope; skipped by applicability.",
        )
