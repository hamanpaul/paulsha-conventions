from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register


_TEST_FILE_GLOBS = ("test_*.py", "*_test.py")

# This is deliberately kept broad for the malformed-YAML fallback.  Parsed
# workflows use token-aware command detection below, so comments and step names
# cannot satisfy R-19.
_CI_TEST_COMMAND = re.compile(
    r"pytest"
    r"|python3?\s+-m\s+unittest"
    r"|unittest\s+discover"
    r"|npm\s+test|pnpm\s+test|yarn\s+test"
    r"|go\s+test|cargo\s+test|ctest|make\s+test",
    re.IGNORECASE,
)
_SHELL_SEPARATOR = re.compile(r"\s*(?:&&|\|\||[;|])\s*")
_INSTALL_COMMAND = re.compile(
    r"^(?:(?:sudo|command)\s+)*(?:"
    r"(?:python(?:3(?:\.\d+)?)?\s+-m\s+)?pip(?:3)?\s+install"
    r"|(?:apt(?:-get)?|apk|dnf|yum)\s+install"
    r"|npm\s+(?:i|install)"
    r"|pnpm\s+(?:add|install)"
    r"|yarn\s+add"
    r")\b",
    re.IGNORECASE,
)
_STEP_OUTPUT_REFERENCE = re.compile(
    r"\bsteps\.([A-Za-z_][A-Za-z0-9_-]*)\.outputs(?:\.|\b)"
)


@dataclass(frozen=True)
class _WorkflowFinding:
    workflow: str
    kind: str
    detail: str


def _has_test_suite(ctx: RuleContext) -> bool:
    tests_dir = ctx.repo_root / "tests"
    if not tests_dir.is_dir():
        return False
    return any(
        True
        for pattern in _TEST_FILE_GLOBS
        for _ in tests_dir.rglob(pattern)
    )


def _strip_shell_comment(line: str) -> str:
    """Remove an unquoted shell comment without changing quoted ``#`` text."""
    quote: str | None = None
    escaped = False
    for index, char in enumerate(line):
        if escaped:
            escaped = False
            continue
        if char == "\\" and quote != "'":
            escaped = True
            continue
        if quote:
            if char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
        elif char == "#":
            return line[:index]
    return line


def _command_tokens(command: str) -> list[str]:
    try:
        tokens = shlex.split(command, comments=False, posix=True)
    except ValueError:
        return []
    while tokens and (tokens[0] in {"!", "sudo", "command"}):
        tokens.pop(0)
    while tokens and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[0]):
        tokens.pop(0)
    return tokens


def _command_runs_tests(command: str) -> bool:
    if _INSTALL_COMMAND.match(command.strip()):
        return False
    tokens = _command_tokens(command)
    if not tokens:
        return False
    executable = tokens[0].lower()
    arguments = [token.lower() for token in tokens[1:]]

    if executable in {"pytest", "py.test"}:
        return True
    if executable in {"python", "python3"} or re.fullmatch(r"python3\.\d+", executable):
        return len(arguments) >= 2 and arguments[0] == "-m" and arguments[1] in {
            "pytest",
            "unittest",
        }
    if executable == "unittest":
        return bool(arguments) and arguments[0] == "discover"
    if executable in {"npm", "pnpm", "yarn"}:
        return bool(arguments) and arguments[0] == "test"
    if executable in {"go", "cargo", "make"}:
        return bool(arguments) and arguments[0] == "test"
    return executable == "ctest"


def _run_has_test_command(run: str) -> bool:
    for raw_line in run.splitlines() or [run]:
        line = _strip_shell_comment(raw_line).strip()
        if not line:
            continue
        if any(_command_runs_tests(part) for part in _SHELL_SEPARATOR.split(line)):
            return True
    return False


def _run_has_legacy_test_match(run: str) -> bool:
    """Recognize only the old comment/install false positives in parsed runs."""
    for raw_line in run.splitlines() or [run]:
        clean_line = _strip_shell_comment(raw_line)
        if _INSTALL_COMMAND.match(clean_line.strip()) and _CI_TEST_COMMAND.search(clean_line):
            return True
        if len(clean_line) < len(raw_line) and _CI_TEST_COMMAND.search(raw_line[len(clean_line):]):
            return True
    return False


def _step_is_high_risk(step: dict[str, Any], step_ids: set[str]) -> bool:
    condition = step.get("if")
    if not condition:
        return False
    if not isinstance(condition, str):
        return False
    return any(match.group(1) in step_ids for match in _STEP_OUTPUT_REFERENCE.finditer(condition))


def _workflow_findings(workflow: Path) -> tuple[list[_WorkflowFinding], bool]:
    """Return findings and whether the YAML parsed as a workflow mapping."""
    text = workflow.read_text(encoding="utf-8", errors="replace")
    try:
        payload = yaml.safe_load(text)
    except yaml.YAMLError:
        if _CI_TEST_COMMAND.search(text):
            return [
                _WorkflowFinding(
                    workflow.name,
                    "parse-fallback",
                    "YAML 解析失敗，已回退整檔字串比對；此命中僅 WARN。",
                )
            ], False
        return [
            _WorkflowFinding(
                workflow.name,
                "parse-error",
                "YAML 解析失敗，未能可靠判定 workflow 內容；此檔案需修正。",
            )
        ], False

    if not isinstance(payload, dict):
        return [], True
    jobs = payload.get("jobs")
    if not isinstance(jobs, dict):
        return [], True

    findings: list[_WorkflowFinding] = []
    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            continue
        steps = job.get("steps")
        if not isinstance(steps, list):
            continue
        step_ids = {
            str(step.get("id"))
            for step in steps
            if isinstance(step, dict) and isinstance(step.get("id"), str)
        }
        for step_index, step in enumerate(steps):
            if not isinstance(step, dict) or not isinstance(step.get("run"), str):
                continue
            run = step["run"]
            has_test = _run_has_test_command(run)
            legacy_match = _run_has_legacy_test_match(run)
            if not has_test and not legacy_match:
                continue
            step_label = str(step.get("name") or step.get("id") or f"step[{step_index}]")
            location = f"{workflow.name}:{job_name}/{step_label}"
            if not has_test:
                findings.append(
                    _WorkflowFinding(
                        workflow.name,
                        "bypass",
                        f"{location} 僅命中註解或安裝行，未確認實際測試執行；下一版將轉 FAIL。",
                    )
                )
                continue
            has_condition = "if" in step
            if has_condition:
                detail = f"{location} 的測試 step 帶 if 條件，gate 可能為條件式。"
                if _step_is_high_risk(step, step_ids):
                    detail += " 可被靜默跳過的高風險樣式。"
                findings.append(_WorkflowFinding(workflow.name, "conditional", detail))
            else:
                findings.append(_WorkflowFinding(workflow.name, "actual", location))
    return findings, True


def _workflow_running_tests(ctx: RuleContext) -> tuple[list[str], list[_WorkflowFinding]]:
    workflows_dir = ctx.repo_root / ".github" / "workflows"
    if not workflows_dir.is_dir():
        return [], []
    actual: list[str] = []
    warnings: list[_WorkflowFinding] = []
    for workflow in sorted(workflows_dir.iterdir()):
        if workflow.suffix not in (".yml", ".yaml") or not workflow.is_file():
            continue
        findings, _parsed = _workflow_findings(workflow)
        for finding in findings:
            if finding.kind == "actual":
                actual.append(finding.workflow)
            else:
                warnings.append(finding)
    return actual, warnings


def _strict_mode(ctx: RuleContext) -> bool:
    r19 = ctx.config.get("r19") if isinstance(ctx.config, dict) else None
    return isinstance(r19, dict) and r19.get("strict") is True


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

        workflow_dir = ctx.repo_root / ".github" / "workflows"
        actual, warnings = _workflow_running_tests(ctx)
        staged_warnings = [
            finding
            for finding in warnings
            if finding.kind in {"bypass", "conditional", "parse-fallback"}
        ]
        if staged_warnings or (actual and warnings):
            report_warnings = warnings if actual else staged_warnings
            detail = "\n".join(f"- {finding.detail}" for finding in report_warnings)
            if _strict_mode(ctx):
                return RuleResult(
                    rule_id=self.rule_id,
                    status=Status.FAIL,
                    message="R-19 strict mode rejected a bypass-prone or conditional test gate.",
                    detail=detail,
                )
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.WARN,
                message="R-19 detected a test gate that may be bypassed or was not parsed reliably.",
                detail=detail,
            )
        if actual:
            workflows = ", ".join(dict.fromkeys(actual))
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message=f"Test suite is executed in CI workflow: {workflows}",
            )

        return RuleResult(
            rule_id=self.rule_id,
            status=Status.FAIL,
            message=(
                "tests/ contains test files but no .github/workflows/* "
                "workflow runs them (expected e.g. pytest / unittest / npm test)."
                if workflow_dir.is_dir()
                else "tests/ contains test files but no .github/workflows/* workflow runs them."
            ),
        )
