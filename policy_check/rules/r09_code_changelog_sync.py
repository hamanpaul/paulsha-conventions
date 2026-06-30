from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register


_PREFIX = "changelog.d/"


def _pr_added_fragment(changed_files: list[str], repo_root: Path) -> bool:
    """True if this PR added/modified a direct ``changelog.d/<name>.md`` fragment.

    Nested paths (``changelog.d/sub/x.md``) are rejected because the release
    collator only collects direct children. The file MUST also still exist at
    HEAD, so a PR that merely *deletes* or *renames* a fragment cannot satisfy
    the gate without actually documenting its change.
    """
    for changed_file in changed_files:
        if not changed_file or not changed_file.startswith(_PREFIX):
            continue
        name = changed_file[len(_PREFIX):]
        if "/" in name or not name.endswith(".md"):
            continue
        if (repo_root / changed_file).is_file():
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

        if _pr_added_fragment(ctx.changed_files, ctx.repo_root):
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
