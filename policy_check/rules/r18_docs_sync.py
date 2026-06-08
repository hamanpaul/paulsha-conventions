from __future__ import annotations

from fnmatch import fnmatch

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register


def _is_docs_change(changed_file: str) -> bool:
    return changed_file == "README.md" or changed_file.startswith("docs/")


@register
class R18DocsSync:
    rule_id = "R-18"
    exempt_label = "policy-exempt:docs-sync"

    def check(self, ctx: RuleContext) -> RuleResult:
        if self.exempt_label in ctx.pr_labels:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.SKIP,
                message=f"R-18 exempted by label: {self.exempt_label}",
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

        if any(_is_docs_change(changed_file) for changed_file in ctx.changed_files):
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message="Code change detected and README.md/docs were updated.",
            )

        return RuleResult(
            rule_id=self.rule_id,
            status=Status.WARN,
            message=(
                "Code changed but no README.md/docs update detected (advisory). "
                "Update docs if behavior changed, or apply the policy-exempt:docs-sync label."
            ),
        )
