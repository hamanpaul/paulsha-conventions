from __future__ import annotations

import re

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register


@register
class R04ChangelogFormat:
    rule_id = "R-04"
    exempt_label = "policy-exempt:changelog-format"

    _required_patterns = {
        "# Changelog": re.compile(r"(?m)^#\s+Changelog\s*$"),
        "## [Unreleased]": re.compile(r"(?m)^##\s+\[Unreleased\]\s*$"),
    }

    def check(self, ctx: RuleContext) -> RuleResult:
        if self.exempt_label in ctx.pr_labels:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.SKIP,
                message=f"Skipped by exemption label: {self.exempt_label}.",
                exempt_label=self.exempt_label,
            )

        changelog = ctx.repo_root / "CHANGELOG.md"
        if not changelog.is_file():
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message="Missing CHANGELOG.md at repository root.",
            )

        text = changelog.read_text(encoding="utf-8", errors="replace")
        missing = [
            marker
            for marker, pattern in self._required_patterns.items()
            if not pattern.search(text)
        ]
        if missing:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message=f"{changelog.name} is missing required sections: {', '.join(missing)}.",
                detail=f"File checked: {changelog.name}",
            )

        return RuleResult(
            rule_id=self.rule_id,
            status=Status.PASS,
            message=f"{changelog.name} includes # Changelog and ## [Unreleased].",
        )
