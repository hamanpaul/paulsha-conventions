from __future__ import annotations

import re

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register

_TEST_FILE_GLOBS = ("test_*.py", "*_test.py")

# 任一 workflow 檔內出現這些指令即視為「CI 有執行測試」。
_CI_TEST_COMMAND = re.compile(
    r"pytest"
    r"|python3?\s+-m\s+unittest"
    r"|unittest\s+discover"
    r"|npm\s+test|pnpm\s+test|yarn\s+test"
    r"|go\s+test|cargo\s+test|ctest|make\s+test"
)


def _has_test_suite(ctx: RuleContext) -> bool:
    tests_dir = ctx.repo_root / "tests"
    if not tests_dir.is_dir():
        return False
    return any(
        True
        for pattern in _TEST_FILE_GLOBS
        for _ in tests_dir.rglob(pattern)
    )


def _workflow_running_tests(ctx: RuleContext) -> str | None:
    workflows_dir = ctx.repo_root / ".github" / "workflows"
    if not workflows_dir.is_dir():
        return None
    for workflow in sorted(workflows_dir.iterdir()):
        if workflow.suffix not in (".yml", ".yaml") or not workflow.is_file():
            continue
        text = workflow.read_text(encoding="utf-8", errors="replace")
        if _CI_TEST_COMMAND.search(text):
            return workflow.name
    return None


@register
class R19CiRunsTests:
    rule_id = "R-19"
    exempt_label = "policy-exempt:ci-tests"

    def check(self, ctx: RuleContext) -> RuleResult:
        if self.exempt_label in ctx.pr_labels:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.SKIP,
                message=f"Skipped by exemption label: {self.exempt_label}.",
                exempt_label=self.exempt_label,
            )

        if not _has_test_suite(ctx):
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message="No test suite detected (tests/ with test files); R-19 not applicable.",
            )

        workflow_name = _workflow_running_tests(ctx)
        if workflow_name:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message=f"Test suite is executed in CI workflow: {workflow_name}",
            )

        return RuleResult(
            rule_id=self.rule_id,
            status=Status.FAIL,
            message=(
                "tests/ contains test files but no .github/workflows/* "
                "workflow runs them (expected e.g. pytest / unittest / npm test)."
            ),
        )
