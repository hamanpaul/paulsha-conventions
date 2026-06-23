from __future__ import annotations

from pathlib import Path

import pytest

from policy_check.rules import registry
from policy_check.rules.base import RuleContext, Status

EXEMPT_LABEL = "policy-exempt:agent-files"


def make_ctx(repo_root: Path, labels: list[str] | None = None) -> RuleContext:
    return RuleContext(
        repo_root=repo_root,
        profile="flat",
        policy_version="1.0.0",
        pr_labels=labels or [],
    )


def get_rule(rule_id: str):
    loaded = {rule.rule_id: rule for rule in registry.load_all()}
    assert rule_id in loaded, f"{rule_id} is not registered"
    return loaded[rule_id]


@pytest.mark.parametrize(
    "fixture_name",
    [
        "agent-files-valid",
    ],
)
def test_r13_pass_when_all_agent_files_present(fixture_repo, fixture_name: str):
    repo = fixture_repo(fixture_name)
    result = get_rule("R-13").check(make_ctx(repo))

    assert result.status == Status.PASS


@pytest.mark.parametrize(
    "fixture_name, expected_text",
    [
        ("missing-agent-files", "missing agent convention files"),
    ],
)
def test_r13_fail_when_missing_agent_file(fixture_repo, fixture_name: str, expected_text: str):
    repo = fixture_repo(fixture_name)
    result = get_rule("R-13").check(make_ctx(repo))

    assert result.status == Status.FAIL
    assert expected_text in result.message


def test_r13_skip_when_exempt_label_present(fixture_repo):
    repo = fixture_repo("missing-agent-files")
    result = get_rule("R-13").check(make_ctx(repo, labels=[EXEMPT_LABEL]))

    assert result.status == Status.SKIP
    assert result.exempt_label == EXEMPT_LABEL


def test_r14_pass_when_policy_versions_match(fixture_repo):
    repo = fixture_repo("agent-files-valid")
    result = get_rule("R-14").check(make_ctx(repo))

    assert result.status == Status.PASS


@pytest.mark.parametrize(
    "fixture_name, expected_text",
    [
        ("agent-version-mismatch/mismatch", "!= declared"),
        ("agent-version-mismatch/missing-declaration", "policy_version not declared"),
    ],
)
def test_r14_fail_when_policy_versions_drift(
    fixture_repo,
    fixture_name: str,
    expected_text: str,
):
    repo = fixture_repo(fixture_name)
    result = get_rule("R-14").check(make_ctx(repo))

    assert result.status == Status.FAIL
    assert expected_text in result.detail


import os


def _symlink_ctx(repo_root, policy_version="1.0.0"):
    return RuleContext(
        repo_root=repo_root,
        profile="flat",
        policy_version=policy_version,
        config={"agent_files": {"mode": "symlink"}},
    )


def _build_symlink_repo(tmp_path, *, canonical_symlink=False, mirror_as_copy=False, wrong_target=False):
    repo = tmp_path / "repo"
    (repo / ".github").mkdir(parents=True)
    if canonical_symlink:
        (repo / "OTHER.md").write_text("policy_version: 1.0.0\n", encoding="utf-8")
        os.symlink("OTHER.md", repo / "CLAUDE.md")
    else:
        (repo / "CLAUDE.md").write_text("policy_version: 1.0.0\n", encoding="utf-8")
    # mirrors
    for name in ("AGENTS.md", "GEMINI.md"):
        if mirror_as_copy and name == "AGENTS.md":
            (repo / name).write_text("policy_version: 1.0.0\n", encoding="utf-8")
        elif wrong_target and name == "AGENTS.md":
            (repo / "DECOY.md").write_text("policy_version: 1.0.0\n", encoding="utf-8")
            os.symlink("DECOY.md", repo / name)
        else:
            os.symlink("CLAUDE.md", repo / name)
    os.symlink("../CLAUDE.md", repo / ".github" / "copilot-instructions.md")
    return repo


def test_r14_symlink_pass_on_valid_topology(tmp_path):
    repo = _build_symlink_repo(tmp_path)
    result = get_rule("R-14").check(_symlink_ctx(repo))
    assert result.status == Status.PASS


def test_r14_symlink_fail_when_mirror_is_copy(tmp_path):
    repo = _build_symlink_repo(tmp_path, mirror_as_copy=True)
    result = get_rule("R-14").check(_symlink_ctx(repo))
    assert result.status == Status.FAIL
    assert "expected symlink" in result.detail


def test_r14_symlink_fail_when_target_wrong(tmp_path):
    repo = _build_symlink_repo(tmp_path, wrong_target=True)
    result = get_rule("R-14").check(_symlink_ctx(repo))
    assert result.status == Status.FAIL
    assert "target mismatch" in result.detail


def test_r14_symlink_fail_when_canonical_is_symlink(tmp_path):
    repo = _build_symlink_repo(tmp_path, canonical_symlink=True)
    result = get_rule("R-14").check(_symlink_ctx(repo))
    assert result.status == Status.FAIL
    assert "canonical must be a regular file" in result.detail
