from __future__ import annotations

import subprocess
from pathlib import Path

from policy_check.rules import registry
from policy_check.rules.base import RuleContext, Status


def _rule():
    return {r.rule_id: r for r in registry.load_all()}["R-24"]


def _git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    return repo


def _commit(repo: Path, msg: str = "c") -> None:
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", msg], check=True)


def _ctx(repo: Path, *, moc=None, changed=None, labels=None, base=None) -> RuleContext:
    return RuleContext(
        repo_root=repo, profile="flat", policy_version="1.0.0",
        config={"moc": moc} if moc else {},
        changed_files=changed or [], pr_labels=labels or [], pr_base_ref=base,
    )


def test_r24_na_when_no_moc(tmp_path):
    repo = _git_repo(tmp_path)
    (repo / "README.md").write_text("x", encoding="utf-8"); _commit(repo)
    assert _rule().check(_ctx(repo)).status == Status.PASS


def test_r24_skip_on_exempt_label(tmp_path):
    repo = _git_repo(tmp_path)
    (repo / "README.md").write_text("x", encoding="utf-8"); _commit(repo)
    result = _rule().check(_ctx(repo, moc={"map": "docs/MOC.md"}, labels=["policy-exempt:moc-alignment"]))
    assert result.status == Status.SKIP
