from __future__ import annotations

import subprocess
from pathlib import Path

from policy_check import config as cfg
from policy_check.rules import registry
from policy_check.rules.base import RuleContext, Status


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _init_repo(repo: Path) -> None:
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")


def _commit(repo: Path, msg: str = "c") -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)
    return subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()


def _write(repo: Path, rel: str, text: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _cfg_text(extra: str = "") -> str:
    return "policy_profile: flat\npolicy_version: 1.0.7\n" + extra


def get_rule():
    loaded = {r.rule_id: r for r in registry.load_all()}
    assert "R-25" in loaded, "R-25 is not registered"
    return loaded["R-25"]


def make_ctx(repo: Path, *, base: str | None = None, labels: list[str] | None = None) -> RuleContext:
    return RuleContext(
        repo_root=repo,
        profile="flat",
        policy_version="1.0.7",
        config=cfg.load(repo),
        pr_labels=labels or [],
        pr_base_ref=base,
    )


# rpc_methods extractor source as YAML (single-quoted scalar embeds double quotes)
_RPC_SRC = (
    "  sources:\n"
    "    - kind: rpc_methods\n"
    "      include: [\"svc.py\"]\n"
    "      pattern: 'method == \"([^\"]+)\"'\n"
)


def test_r25_not_applicable_passes(tmp_path):
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text())
    _commit(tmp_path)
    assert get_rule().check(make_ctx(tmp_path)).status == Status.PASS


def test_r25_all_mode_unmentioned_fact_fails(tmp_path):
    extra = "doc_coverage:\n  mode: all\n  targets: [\"README.md\"]\n" + _RPC_SRC
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text(extra))
    _write(tmp_path, "svc.py", 'if method == "session.renumber":\n    pass\n')
    _write(tmp_path, "README.md", "# docs\nno mention here\n")
    _commit(tmp_path)
    res = get_rule().check(make_ctx(tmp_path))
    assert res.status == Status.FAIL
    assert "session.renumber" in res.detail


def test_r25_all_mode_mentioned_passes(tmp_path):
    extra = "doc_coverage:\n  mode: all\n  targets: [\"README.md\"]\n" + _RPC_SRC
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text(extra))
    _write(tmp_path, "svc.py", 'if method == "session.renumber":\n    pass\n')
    _write(tmp_path, "README.md", "# docs\nsupports `session.renumber`\n")
    _commit(tmp_path)
    assert get_rule().check(make_ctx(tmp_path)).status == Status.PASS


def test_r25_changed_mode_only_checks_new_facts(tmp_path):
    extra = "doc_coverage:\n  mode: changed\n  targets: [\"README.md\"]\n" + _RPC_SRC
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text(extra))
    _write(tmp_path, "svc.py", 'if method == "session.close":\n    pass\n')
    _write(tmp_path, "README.md", "# docs\nno mentions\n")
    base = _commit(tmp_path, "base")
    # this PR adds a new method and documents only the new one
    _write(tmp_path, "svc.py",
           'if method == "session.close":\n    pass\nif method == "session.renumber":\n    pass\n')
    _write(tmp_path, "README.md", "# docs\nadds `session.renumber`\n")
    _commit(tmp_path, "head")
    res = get_rule().check(make_ctx(tmp_path, base=base))
    assert res.status == Status.PASS  # pre-existing session.close must not be required


def test_r25_changed_mode_without_base_warns(tmp_path):
    extra = "doc_coverage:\n  mode: changed\n  targets: [\"README.md\"]\n" + _RPC_SRC
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text(extra))
    _write(tmp_path, "svc.py", 'if method == "session.renumber":\n    pass\n')
    _write(tmp_path, "README.md", "# docs\nnone\n")
    _commit(tmp_path)
    res = get_rule().check(make_ctx(tmp_path))  # no base ref
    assert res.status == Status.WARN


def test_r25_changed_mode_new_unmentioned_fails(tmp_path):
    extra = "doc_coverage:\n  mode: changed\n  targets: [\"README.md\"]\n" + _RPC_SRC
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text(extra))
    _write(tmp_path, "svc.py", 'if method == "session.close":\n    pass\n')
    _write(tmp_path, "README.md", "# docs\n`session.close`\n")
    base = _commit(tmp_path, "base")
    _write(tmp_path, "svc.py",
           'if method == "session.close":\n    pass\nif method == "session.renumber":\n    pass\n')
    _commit(tmp_path, "head")
    res = get_rule().check(make_ctx(tmp_path, base=base))
    assert res.status == Status.FAIL
    assert "session.renumber" in res.detail


def test_r25_target_out_of_doc_scope_fails(tmp_path):
    extra = "doc_coverage:\n  mode: all\n  targets: [\"CLAUDE.md\"]\n" + _RPC_SRC
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text(extra))
    _write(tmp_path, "svc.py", 'if method == "session.renumber":\n    pass\n')
    _write(tmp_path, "CLAUDE.md", "# claude\n")
    _commit(tmp_path)
    res = get_rule().check(make_ctx(tmp_path))
    assert res.status == Status.FAIL
    assert "CLAUDE.md" in res.message


def test_r25_missing_target_doc_fails(tmp_path):
    extra = "doc_coverage:\n  mode: all\n  targets: [\"docs/missing.md\"]\n" + _RPC_SRC
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text(extra))
    _write(tmp_path, "svc.py", 'if method == "session.renumber":\n    pass\n')
    _commit(tmp_path)
    res = get_rule().check(make_ctx(tmp_path))
    assert res.status == Status.FAIL


def test_r25_invalid_extractor_config_fails(tmp_path):
    extra = (
        "doc_coverage:\n  mode: all\n  targets: [\"README.md\"]\n"
        "  sources:\n    - kind: rpc_methods\n      include: [\"svc.py\"]\n"  # missing pattern
    )
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text(extra))
    _write(tmp_path, "svc.py", "x = 1\n")
    _write(tmp_path, "README.md", "# d\n")
    _commit(tmp_path)
    res = get_rule().check(make_ctx(tmp_path))
    assert res.status == Status.FAIL
    assert "pattern" in (res.message + res.detail)


def test_r25_substring_does_not_count_as_coverage(tmp_path):
    extra = (
        "doc_coverage:\n  mode: all\n  targets: [\"README.md\"]\n"
        "  sources:\n    - kind: modules\n      include: [\"pkg/*.py\"]\n"
    )
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text(extra))
    _write(tmp_path, "pkg/auth.py", "x = 1\n")
    _write(tmp_path, "README.md", "see pkg/auth.python for helpers\n")  # substring only
    _commit(tmp_path)
    res = get_rule().check(make_ctx(tmp_path))
    assert res.status == Status.FAIL
    assert "pkg/auth.py" in res.detail


def test_r25_cli_tree_all_mode_unmentioned_fails(tmp_path):
    extra = (
        "doc_coverage:\n  mode: all\n  targets: [\"README.md\"]\n"
        "  sources:\n    - kind: cli_tree\n      command: \"python3 printcli.py\"\n"
    )
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text(extra))
    _write(tmp_path, "printcli.py", "print('app sync now')\n")
    _write(tmp_path, "README.md", "# d\nno mention\n")
    _commit(tmp_path)
    res = get_rule().check(make_ctx(tmp_path))
    assert res.status == Status.FAIL
    assert "app sync now" in res.detail


def test_r25_changed_mode_no_base_does_not_run_or_fail_on_cli_tree(tmp_path):
    # C1: in changed mode with no resolvable base, a failing cli_tree command must
    # not turn the required WARN into a FAIL (and must not run at all).
    extra = (
        "doc_coverage:\n  mode: changed\n  targets: [\"README.md\"]\n"
        "  sources:\n    - kind: cli_tree\n      command: \"python3 failing.py\"\n"
    )
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text(extra))
    _write(tmp_path, "failing.py", "import sys\nsys.exit(7)\n")
    _write(tmp_path, "README.md", "# d\nno mention\n")
    _commit(tmp_path)
    res = get_rule().check(make_ctx(tmp_path))  # no base
    assert res.status == Status.WARN


def test_r25_changed_mode_with_base_ignores_cli_tree(tmp_path):
    # C1: in changed mode with a base, cli_tree is not executed, so a failing
    # cli command cannot FAIL the rule; only newly-added file facts are gated.
    extra = (
        "doc_coverage:\n  mode: changed\n  targets: [\"README.md\"]\n"
        + _RPC_SRC
        + "    - kind: cli_tree\n      command: \"python3 failing.py\"\n"
    )
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text(extra))
    _write(tmp_path, "failing.py", "import sys\nsys.exit(7)\n")
    _write(tmp_path, "svc.py", 'if method == "session.close":\n    pass\n')
    _write(tmp_path, "README.md", "# d\n")
    base = _commit(tmp_path, "base")
    _write(tmp_path, "svc.py",
           'if method == "session.close":\n    pass\nif method == "session.renumber":\n    pass\n')
    _write(tmp_path, "README.md", "# d\nadds `session.renumber`\n")
    _commit(tmp_path, "head")
    res = get_rule().check(make_ctx(tmp_path, base=base))
    assert res.status == Status.PASS
