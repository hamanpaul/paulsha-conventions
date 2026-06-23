from __future__ import annotations

from pathlib import Path

from policy_check.rules import registry
from policy_check.rules.base import RuleContext, Status

REPO = "hamanpaul/paulsha-conventions"
ENGINE = f"{REPO}/.github/workflows/reusable-policy-check.yml"


def _rule():
    return {r.rule_id: r for r in registry.load_all()}["R-23"]


def _ctx(repo_root: Path, *, policy_version="1.0.5", configured=True, labels=None):
    config = {"conventions_engine": {"repo": REPO}} if configured else {}
    return RuleContext(
        repo_root=repo_root,
        profile="flat",
        policy_version=policy_version,
        config=config,
        pr_labels=labels or [],
    )


def _wf(tmp_path: Path, uses_line: str):
    d = tmp_path / ".github" / "workflows"
    d.mkdir(parents=True, exist_ok=True)
    (d / "policy-check.yml").write_text(f"jobs:\n  check:\n    {uses_line}\n", encoding="utf-8")
    return tmp_path


def test_r23_pass_on_tag_match(tmp_path):
    repo = _wf(tmp_path, f"uses: {ENGINE}@v1.0.5")
    assert _rule().check(_ctx(repo)).status == Status.PASS


def test_r23_fail_on_tag_mismatch(tmp_path):
    repo = _wf(tmp_path, f"uses: {ENGINE}@v1.0.2")
    result = _rule().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "1.0.2" in result.detail and "1.0.5" in result.detail


def test_r23_pass_on_sha_with_matching_comment(tmp_path):
    sha = "a" * 40
    repo = _wf(tmp_path, f"uses: {ENGINE}@{sha}  # v1.0.5")
    assert _rule().check(_ctx(repo)).status == Status.PASS


def test_r23_fail_on_sha_with_mismatching_comment(tmp_path):
    sha = "a" * 40
    repo = _wf(tmp_path, f"uses: {ENGINE}@{sha}  # v1.0.2")
    assert _rule().check(_ctx(repo)).status == Status.FAIL


def test_r23_warn_on_bare_sha(tmp_path):
    sha = "b" * 40
    repo = _wf(tmp_path, f"uses: {ENGINE}@{sha}")
    assert _rule().check(_ctx(repo)).status == Status.WARN


def test_r23_na_on_local_uses(tmp_path):
    repo = _wf(tmp_path, "uses: ./.github/workflows/reusable-policy-check.yml")
    assert _rule().check(_ctx(repo)).status == Status.PASS


def test_r23_na_when_engine_not_configured(tmp_path):
    repo = _wf(tmp_path, f"uses: {ENGINE}@v1.0.2")
    assert _rule().check(_ctx(repo, configured=False)).status == Status.PASS


def test_r23_skip_on_exempt_label(tmp_path):
    repo = _wf(tmp_path, f"uses: {ENGINE}@v1.0.2")
    result = _rule().check(_ctx(repo, labels=["policy-exempt:engine-pin"]))
    assert result.status == Status.SKIP
