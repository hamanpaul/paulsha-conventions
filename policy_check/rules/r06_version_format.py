from __future__ import annotations

import re

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register


@register
class R06VersionFormat:
    rule_id = "R-06"
    exempt_label = None

    _version_pattern = re.compile(r"^\d+\.\d+\.\d+(-fix\.\d+)?$")

    def check(self, ctx: RuleContext) -> RuleResult:
        version_file = ctx.repo_root / "VERSION"
        if not version_file.is_file():
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message="Missing VERSION at repository root.",
                detail="Checked: VERSION",
            )

        version = version_file.read_text(encoding="utf-8", errors="replace").strip()
        if self._version_pattern.fullmatch(version):
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message=f"VERSION format is valid: {version}",
            )

        return RuleResult(
            rule_id=self.rule_id,
            status=Status.FAIL,
            message=(
                "Invalid VERSION format. Expected "
                "<MAJOR>.<MINOR>.<PATCH>(-fix.N)?"
            ),
            detail=f"Pattern: {self._version_pattern.pattern}; got: {version!r}",
        )
