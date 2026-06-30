from __future__ import annotations

from fnmatch import fnmatch

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register


def _pr_added_fragment(changed_files: list[str]) -> bool:
    """True if this PR touched a changelog.d/*.md fragment (excluding .gitkeep)."""
    for changed_file in changed_files:
        if (
            changed_file
            and fnmatch(changed_file, "changelog.d/*.md")
            and not changed_file.endswith("/.gitkeep")
        ):
            return True
    return False


@register
class R09CodeChangelogSync:
    rule_id = "R-09"
    exempt_label = "skip-changelog"

    def check(self, ctx: RuleContext) -> RuleResult:
        if self.exempt_label in ctx.pr_labels:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.SKIP,
                message=f"Skipped by exemption label: {self.exempt_label}.",
                exempt_label=self.exempt_label,
            )

        code_paths = ctx.config.get("code_paths") or []
        has_code_change = any(
            any(changed_file and fnmatch(changed_file, pattern) for pattern in code_paths)
            for changed_file in ctx.changed_files
        )

        if not has_code_change:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message="No code path files changed.",
            )

        if _pr_added_fragment(ctx.changed_files):
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message="Code change detected and a changelog.d fragment was added.",
            )

        return RuleResult(
            rule_id=self.rule_id,
            status=Status.FAIL,
            message=(
                "Code files changed but no changelog.d/*.md fragment was added "
                "(add a fragment, or apply the skip-changelog label)."
            ),
        )
