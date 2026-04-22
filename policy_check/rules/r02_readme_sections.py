from __future__ import annotations

import re

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register


@register
class R02ReadmeSections:
    rule_id = "R-02"
    exempt_label = "policy-exempt:readme-sections"

    _required_sections = ("Install", "Usage", "Version")

    def check(self, ctx: RuleContext) -> RuleResult:
        if self.exempt_label in ctx.pr_labels:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.SKIP,
                message=f"R-02 exempted by label: {self.exempt_label}",
                exempt_label=self.exempt_label,
            )

        readme_path = ctx.repo_root / "README.md"
        if not readme_path.is_file():
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message="README.md missing (see R-01).",
            )

        text = readme_path.read_text(encoding="utf-8")
        headings = {
            section.strip()
            for section in re.findall(r"^##\s+([^\n]+?)\s*$", text, flags=re.MULTILINE)
        }
        missing = [section for section in self._required_sections if section not in headings]

        if missing:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message=f"README missing required sections: {missing}",
                detail=(
                    f"expected ## headings: {list(self._required_sections)}; "
                    f"found: {sorted(headings)}"
                ),
            )

        return RuleResult(
            rule_id=self.rule_id,
            status=Status.PASS,
            message=f"README has all required sections: {list(self._required_sections)}",
        )
