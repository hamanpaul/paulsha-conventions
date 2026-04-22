from __future__ import annotations

import re
from fnmatch import fnmatch

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register


def _unreleased_has_bullet_entry(changelog_text: str) -> bool:
    match = re.search(
        r"^##\s+\[Unreleased\]\s*(.*?)(?=^##\s+\[|\Z)",
        changelog_text,
        flags=re.MULTILINE | re.DOTALL,
    )
    if not match:
        return False

    section_body = match.group(1)
    return bool(re.search(r"^\s*-\s+\S", section_body, flags=re.MULTILINE))


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
            any(fnmatch(changed_file, pattern) for pattern in code_paths)
            for changed_file in ctx.changed_files
        )

        if not has_code_change:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message="No code path files changed.",
            )

        changelog_path = ctx.repo_root / "CHANGELOG.md"
        if not changelog_path.is_file():
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message="Code files changed but CHANGELOG.md is missing.",
            )

        changelog_text = changelog_path.read_text(encoding="utf-8", errors="replace")
        if not _unreleased_has_bullet_entry(changelog_text):
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message="Code files changed but [Unreleased] has no bullet entry.",
            )

        return RuleResult(
            rule_id=self.rule_id,
            status=Status.PASS,
            message="Code change detected and [Unreleased] includes an entry.",
        )
