from __future__ import annotations

from pathlib import Path

from policy_check.rules import registry
from policy_check.rules.base import RuleContext, Status


def make_ctx(repo_root: Path, labels: list[str] | None = None) -> RuleContext:
    return RuleContext(
        repo_root=repo_root,
        profile="flat",
        policy_version="1.0.2",
        pr_labels=labels or [],
    )


def get_rule():
    loaded = {rule.rule_id: rule for rule in registry.load_all()}
    assert "R-19" in loaded, "R-19 is not registered"
    return loaded["R-19"]


def test_r19_pass_when_suite_and_ci(fixture_repo):
    repo = fixture_repo("ci-tests/with-suite-and-ci")
    result = get_rule().check(make_ctx(repo))
    assert result.status == Status.PASS
    assert "tests.yml" in result.message


def test_r19_fail_when_suite_without_ci(fixture_repo):
    repo = fixture_repo("ci-tests/with-suite-no-ci")
    result = get_rule().check(make_ctx(repo))
    assert result.status == Status.FAIL
    assert "no .github/workflows" in result.message


def test_r19_pass_vacuously_without_suite(fixture_repo):
    repo = fixture_repo("ci-tests/no-suite")
    result = get_rule().check(make_ctx(repo))
    assert result.status == Status.PASS
    assert "not applicable" in result.message


def test_r19_fail_when_workflows_dir_missing(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_sample.py").write_text(
        "def test_sample():\n    assert True\n", encoding="utf-8"
    )
    result = get_rule().check(make_ctx(tmp_path))
    assert result.status == Status.FAIL


def test_r19_skip_with_exemption_label(fixture_repo):
    repo = fixture_repo("ci-tests/with-suite-no-ci")
    result = get_rule().check(make_ctx(repo, labels=["policy-exempt:ci-tests"]))
    assert result.status == Status.SKIP
    assert result.exempt_label == "policy-exempt:ci-tests"
