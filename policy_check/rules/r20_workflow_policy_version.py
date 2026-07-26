from __future__ import annotations

import re

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register

# 同時涵蓋 reusable-workflow caller 的 `policy_version: "1.0.2"` 與
# env 風格的 `POLICY_VERSION: "1.0.2"`；只匹配 semver 字面值，
# 不會誤傷 input 宣告（無值）或 `${{ inputs.policy_version }}` 模板表達式。
_WORKFLOW_POLICY_VERSION = re.compile(
    r"(?im)^\s*policy_version:\s*[\"']?(\d+\.\d+\.\d+(?:-fix\.\d+)?)[\"']?\s*$"
)


@register
class R20WorkflowPolicyVersionSync:
    rule_id = "R-20"
    exempt_label = None

    def check(self, ctx: RuleContext) -> RuleResult:
        workflows_dir = ctx.repo_root / ".github" / "workflows"
        if not workflows_dir.is_dir():
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message="No .github/workflows directory; R-20 not applicable.",
            )

        declared: list[tuple[str, str]] = []
        for workflow in sorted(workflows_dir.iterdir()):
            if workflow.suffix not in (".yml", ".yaml") or not workflow.is_file():
                continue
            text = workflow.read_text(encoding="utf-8", errors="replace")
            for match in _WORKFLOW_POLICY_VERSION.finditer(text):
                declared.append((workflow.name, match.group(1)))

        if not declared:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message="No workflow declares a policy_version literal; R-20 not applicable.",
            )

        mismatched = [
            (name, version)
            for name, version in declared
            if version != ctx.policy_version
        ]
        if mismatched:
            detail = "\n".join(
                f"{name}: declares {version}, project policy has {ctx.policy_version}"
                for name, version in mismatched
            )
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message=(
                    f"Workflow policy_version out of sync with project config "
                    f"({len(mismatched)} mismatch)."
                ),
                detail=detail,
            )

        return RuleResult(
            rule_id=self.rule_id,
            status=Status.PASS,
            message=(
                f"All workflow policy_version declarations match {ctx.policy_version}."
            ),
        )
