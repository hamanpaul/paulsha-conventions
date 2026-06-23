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


def test_r24_warn_when_trigger_changed_but_static_not(tmp_path):
    repo = _git_repo(tmp_path)
    (repo / "README.md").write_text("x", encoding="utf-8"); _commit(repo)
    moc = {"static": "docs/ctx.yml", "triggers": ["Dockerfile*"]}
    result = _rule().check(_ctx(repo, moc=moc, changed=["Dockerfile"]))
    assert result.status == Status.WARN
    assert "docs/ctx.yml" in result.detail


def test_r24_pass_when_static_updated_with_trigger(tmp_path):
    repo = _git_repo(tmp_path)
    (repo / "README.md").write_text("x", encoding="utf-8"); _commit(repo)
    moc = {"static": "docs/ctx.yml", "triggers": ["Dockerfile*"]}
    result = _rule().check(_ctx(repo, moc=moc, changed=["Dockerfile", "docs/ctx.yml"]))
    assert result.status == Status.PASS


def test_r24_warn_on_chronic_dangling_link(tmp_path):
    repo = _git_repo(tmp_path)
    (repo / "docs").mkdir()
    (repo / "docs" / "MOC.md").write_text("[p](../docs/superpowers/plans/gone.md)", encoding="utf-8")
    _commit(repo)  # gone.md never existed → chronic
    result = _rule().check(_ctx(repo, moc={"map": "docs/MOC.md"}))
    assert result.status == Status.WARN
    assert "gone.md" in result.detail


def test_r24_fail_on_dangling_introduced_this_change(tmp_path):
    repo = _git_repo(tmp_path)
    plans = repo / "docs" / "superpowers" / "plans"
    plans.mkdir(parents=True)
    (plans / "p.md").write_text("plan", encoding="utf-8")
    (repo / "docs" / "MOC.md").write_text("[p](superpowers/plans/p.md)", encoding="utf-8")
    _commit(repo, "base")
    subprocess.run(["git", "-C", str(repo), "branch", "base"], check=True)
    (plans / "p.md").unlink()  # remove the target this change
    _commit(repo, "head")
    result = _rule().check(_ctx(repo, moc={"map": "docs/MOC.md"}, base="base"))
    assert result.status == Status.FAIL
    assert "p.md" in result.detail


def test_r24_warn_on_orphan_plan(tmp_path):
    repo = _git_repo(tmp_path)
    plans = repo / "docs" / "superpowers" / "plans"; plans.mkdir(parents=True)
    (plans / "p.md").write_text("plan", encoding="utf-8")
    (repo / "docs" / "MOC.md").write_text("（空地圖，沒 link 到 p.md）", encoding="utf-8")
    _commit(repo)
    result = _rule().check(_ctx(repo, moc={"map": "docs/MOC.md"}))
    assert result.status == Status.WARN
    assert "p.md" in result.detail


def test_r24_pass_when_plan_linked(tmp_path):
    repo = _git_repo(tmp_path)
    plans = repo / "docs" / "superpowers" / "plans"; plans.mkdir(parents=True)
    (plans / "p.md").write_text("plan", encoding="utf-8")
    (repo / "docs" / "MOC.md").write_text("[p](superpowers/plans/p.md)", encoding="utf-8")
    _commit(repo)
    result = _rule().check(_ctx(repo, moc={"map": "docs/MOC.md"}))
    assert result.status == Status.PASS


def test_r24_fail_on_path_token_dangling_introduced_this_change(tmp_path):
    # backtick path token（非 markdown link）也須掃，本次移除 → FAIL
    repo = _git_repo(tmp_path)
    plans = repo / "docs" / "superpowers" / "plans"; plans.mkdir(parents=True)
    (plans / "p.md").write_text("plan", encoding="utf-8")
    (repo / "docs" / "MOC.md").write_text("see `superpowers/plans/p.md`", encoding="utf-8")
    _commit(repo, "base")
    subprocess.run(["git", "-C", str(repo), "branch", "base"], check=True)
    (plans / "p.md").unlink()
    _commit(repo, "head")
    result = _rule().check(_ctx(repo, moc={"map": "docs/MOC.md"}, base="base"))
    assert result.status == Status.FAIL
    assert "p.md" in result.detail


def test_r24_warn_on_declared_but_missing_map(tmp_path):
    repo = _git_repo(tmp_path)
    (repo / "README.md").write_text("x", encoding="utf-8"); _commit(repo)
    result = _rule().check(_ctx(repo, moc={"map": "docs/NOPE.md"}))
    assert result.status == Status.WARN
    assert "NOPE.md" in result.detail


def test_r24_no_crash_on_non_str_map(tmp_path):
    # malformed config（R-08 會 FAIL，但 R-24 不得 crash）
    repo = _git_repo(tmp_path)
    (repo / "README.md").write_text("x", encoding="utf-8"); _commit(repo)
    result = _rule().check(_ctx(repo, moc={"map": ["docs/MOC.md"]}))
    assert result.status in (Status.PASS, Status.WARN)
