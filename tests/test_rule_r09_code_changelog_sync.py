from __future__ import annotations

from pathlib import Path

import pytest

from policy_check.rules import registry
from policy_check.rules.base import RuleContext, Status


def make_ctx(
    repo_root: Path,
    changed_files: list[str] | None = None,
    labels: list[str] | None = None,
) -> RuleContext:
    return RuleContext(
        repo_root=repo_root,
        profile="flat",
        policy_version="1.0.0",
        config={"code_paths": ["**/*.py", "**/*.sh", "scripts/**"]},
        changed_files=changed_files or [],
        pr_labels=labels or [],
    )


def get_rule(rule_id: str):
    loaded = {rule.rule_id: rule for rule in registry.load_all()}
    assert rule_id in loaded, f"{rule_id} is not registered"
    return loaded[rule_id]


@pytest.mark.parametrize(
    "fixture_name, changed_files, labels, expected",
    [
        ("code-changelog-synced", ["src/foo.py"], [], Status.PASS),
        ("code-no-changelog", ["src/foo.py"], [], Status.FAIL),
        ("code-no-changelog", ["src/foo.py"], ["skip-changelog"], Status.SKIP),
        ("code-no-changelog", ["docs/x.md"], [], Status.PASS),
    ],
)
def test_r09_code_changelog_sync(
    fixture_repo,
    fixture_name: str,
    changed_files: list[str],
    labels: list[str],
    expected: Status,
):
    repo = fixture_repo(fixture_name)
    result = get_rule("R-09").check(make_ctx(repo, changed_files=changed_files, labels=labels))

    assert result.status == expected, result.message
    if expected == Status.FAIL:
        assert "[Unreleased]" in result.message
    if expected == Status.SKIP:
        assert result.exempt_label == "skip-changelog"
