from __future__ import annotations

from pathlib import Path

from policy_check.rules import registry
from policy_check.rules.base import RuleContext, Status


def make_ctx(
    repo_root: Path,
    changed_files: list[str] | None = None,
    labels: list[str] | None = None,
    *,
    config: dict | None = None,
) -> RuleContext:
    return RuleContext(
        repo_root=repo_root,
        profile="flat",
        policy_version="1.0.1",
        config=config or {"code_paths": ["**/*.py", "**/*.sh", "scripts/**"]},
        changed_files=changed_files or [],
        pr_labels=labels or [],
    )


def get_rule(rule_id: str):
    loaded = {rule.rule_id: rule for rule in registry.load_all()}
    assert rule_id in loaded, f"{rule_id} is not registered"
    return loaded[rule_id]


def test_r18_pass_when_no_code_change(tmp_path):
    result = get_rule("R-18").check(make_ctx(tmp_path, changed_files=["docs/x.md"]))

    assert result.status == Status.PASS


def test_r18_skip_on_exempt_label(tmp_path):
    result = get_rule("R-18").check(
        make_ctx(tmp_path, changed_files=["src/foo.py"], labels=["policy-exempt:docs-sync"])
    )

    assert result.status == Status.SKIP
    assert result.exempt_label == "policy-exempt:docs-sync"


def test_r18_pass_when_code_change_with_readme(tmp_path):
    result = get_rule("R-18").check(
        make_ctx(tmp_path, changed_files=["policy_check/foo.py", "README.md"])
    )

    assert result.status == Status.PASS


def test_r18_pass_when_code_change_with_docs_dir(tmp_path):
    result = get_rule("R-18").check(
        make_ctx(tmp_path, changed_files=["scripts/run.sh", "docs/guide.md"])
    )

    assert result.status == Status.PASS


def test_r18_warn_when_code_change_without_docs(tmp_path):
    result = get_rule("R-18").check(make_ctx(tmp_path, changed_files=["policy_check/foo.py"]))

    assert result.status == Status.WARN
    assert "docs" in result.message.lower()


def test_r18_pass_when_code_change_with_custom_doc_path(tmp_path):
    result = get_rule("R-18").check(
        make_ctx(
            tmp_path,
            changed_files=["policy_check/foo.py", "CLAUDE.md"],
            config={
                "code_paths": ["**/*.py", "**/*.sh", "scripts/**"],
                "doc_paths": ["README.md", "docs/**", "CLAUDE.md"],
            },
        )
    )
    assert result.status == Status.PASS


def test_r18_warn_when_custom_doc_path_not_touched(tmp_path):
    result = get_rule("R-18").check(
        make_ctx(
            tmp_path,
            changed_files=["policy_check/foo.py"],
            config={
                "code_paths": ["**/*.py", "**/*.sh", "scripts/**"],
                "doc_paths": ["README.md", "docs/**", "CLAUDE.md"],
            },
        )
    )
    assert result.status == Status.WARN
