from __future__ import annotations

from pathlib import Path

from policy_check.rules import registry
from policy_check.rules.base import RuleContext, Status


def make_ctx(
    repo_root: Path,
    labels: list[str] | None = None,
    config: dict | None = None,
) -> RuleContext:
    return RuleContext(
        repo_root=repo_root,
        profile="flat",
        policy_version="1.0.2",
        config=config or {},
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


def test_r19_warns_when_only_comment_mentions_pytest(fixture_repo):
    repo = fixture_repo("ci-tests/comment-only")
    result = get_rule().check(make_ctx(repo))
    assert result.status == Status.WARN
    assert "下一版將轉 FAIL" in result.detail


def test_r19_warns_when_only_install_line_mentions_pytest(fixture_repo):
    repo = fixture_repo("ci-tests/install-only")
    result = get_rule().check(make_ctx(repo))
    assert result.status == Status.WARN
    assert "安裝行" in result.detail


def test_r19_warns_when_test_step_has_conditional_guard(fixture_repo):
    repo = fixture_repo("ci-tests/conditional-skip")
    result = get_rule().check(make_ctx(repo))
    assert result.status == Status.WARN
    assert "條件式" in result.detail
    assert "可被靜默跳過的高風險樣式" in result.detail


def test_r19_strict_mode_fails_bypass_warning(fixture_repo):
    repo = fixture_repo("ci-tests/comment-only")
    result = get_rule().check(make_ctx(repo, config={"r19": {"strict": True}}))
    assert result.status == Status.FAIL
    assert "strict mode" in result.message


def test_r19_pass_when_run_line_has_quoted_pipe(fixture_repo):
    # Regression: a single `|` used to be treated as a shell separator, so a
    # quoted pipe inside a run line's own arguments (e.g. `-k "a|b"`) split the
    # command mid-quote. shlex then failed on both unbalanced-quote halves and
    # the real `pytest` invocation went undetected (false negative). Only
    # `&&` / `||` / `;` are separators now.
    repo = fixture_repo("ci-tests/quoted-pipe")
    result = get_rule().check(make_ctx(repo))
    assert result.status == Status.PASS
    assert "tests.yml" in result.message


def test_r19_falls_back_to_string_matching_for_invalid_yaml(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_sample.py").write_text("def test_sample():\n    assert True\n", encoding="utf-8")
    workflow_dir = tmp_path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    (workflow_dir / "broken.yml").write_text(
        "jobs:\n  test: [\n    run: pytest\n", encoding="utf-8"
    )
    result = get_rule().check(make_ctx(tmp_path))
    assert result.status == Status.WARN
    assert "回退整檔字串比對" in result.detail
