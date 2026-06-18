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
    return "policy_profile: flat\npolicy_version: 1.0.4\ntier: shareable\n" + extra


def get_rule():
    loaded = {r.rule_id: r for r in registry.load_all()}
    assert "R-22" in loaded, "R-22 is not registered"
    return loaded["R-22"]


def make_ctx(repo: Path, *, base: str | None = None, labels: list[str] | None = None) -> RuleContext:
    return RuleContext(
        repo_root=repo,
        profile="flat",
        policy_version="1.0.4",
        config=cfg.load(repo),
        pr_labels=labels or [],
        pr_base_ref=base,
    )


def test_r22_clean_repo_passes(tmp_path):
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text())
    _write(tmp_path, "docs/guide.md", "see [rule](../policy_check/rules/r08_policy_config_schema.py)\n")
    _write(tmp_path, "policy_check/rules/r08_policy_config_schema.py", "x = 1\n")
    _commit(tmp_path)
    assert get_rule().check(make_ctx(tmp_path)).status == Status.PASS


def test_r22_dangling_link_without_base_is_warn(tmp_path):
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text())
    _write(tmp_path, "docs/guide.md", "see [gone](./missing_module.py)\n")
    _commit(tmp_path)
    res = get_rule().check(make_ctx(tmp_path))  # no base → cannot prove new breakage
    assert res.status == Status.WARN
    assert "missing_module.py" in res.detail


def test_r22_dangling_path_token_warn(tmp_path):
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text())
    _write(tmp_path, "README.md", "run `policy_check/rules/r99_ghost.py` first\n")
    _commit(tmp_path)
    assert get_rule().check(make_ctx(tmp_path)).status == Status.WARN


def test_r22_skip_with_exemption_label(tmp_path):
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text())
    _write(tmp_path, "docs/guide.md", "[gone](./missing.py)\n")
    _commit(tmp_path)
    res = get_rule().check(make_ctx(tmp_path, labels=["policy-exempt:doc-reference"]))
    assert res.status == Status.SKIP
    assert res.exempt_label == "policy-exempt:doc-reference"


def test_r22_respects_allow_glob(tmp_path):
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text("doc_reference:\n  allow: [\"docs/legacy/**\"]\n"))
    _write(tmp_path, "docs/legacy/old.md", "[gone](./missing.py)\n")
    _commit(tmp_path)
    assert get_rule().check(make_ctx(tmp_path)).status == Status.PASS


def test_r22_excludes_spec_trees(tmp_path):
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text())
    _write(tmp_path, "docs/superpowers/specs/x.md", "[future](./not_yet.py)\n")
    _write(tmp_path, "openspec/changes/y/proposal.md", "[future](./not_yet.py)\n")
    _commit(tmp_path)
    assert get_rule().check(make_ctx(tmp_path)).status == Status.PASS
