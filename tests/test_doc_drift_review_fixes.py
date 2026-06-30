"""對 #25 code-review + codex 對抗式 findings 的回歸測試。"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from policy_check.doc_drift import coverage, drift, engine, exempt, symbols

REPO = Path(__file__).resolve().parents[1]


def _git(repo: Path, *a):
    subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)


def _init(repo: Path) -> None:
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")


def _head(repo: Path) -> str:
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()


# F：parse_ctags_json 對「合法 JSON 但非物件」的行不得崩潰
def test_parse_ctags_json_skips_valid_non_dict_lines():
    lines = [
        "123",
        '"a bare string"',
        "[1, 2, 3]",
        "true",
        '{"_type":"tag","name":"keep","language":"Python","kind":"function"}',
    ]
    got = symbols.parse_ctags_json(lines)  # 不應拋 AttributeError
    assert ("Python", "function", "", "keep") in got


# H：inline marker 僅承認 HTML 註解形式，避免內文字面誤抑制
def test_line_is_ignored_requires_comment_form():
    assert exempt.line_is_ignored("call `gone` <!-- doc-drift-ignore -->") is True
    assert exempt.line_is_ignored("<!--doc-drift-ignore-->") is True
    assert exempt.line_is_ignored("the token doc-drift-ignore appears in prose") is False
    assert exempt.line_is_ignored("`doc-drift-ignore`") is False


# E：DEFAULT_GOVERNED_PREFIXES 沿用重構前廣義 docs/superpowers/（不偷偷收窄）
def test_default_governed_prefixes_preserve_broad_docs_superpowers():
    assert "docs/superpowers/" in coverage.DEFAULT_GOVERNED_PREFIXES
    # 廣義前綴可涵蓋根層 .md（重構前 _GOVERNED_PREFIXES 行為）
    assert coverage.orphans({"docs/superpowers/x.md"}, set()) == ["docs/superpowers/x.md"]


# I：被 inline-ignore 的行上的 map 連結，仍須算「已連結」，不得誤判 orphan
def test_run_moc_link_on_ignored_line_still_counts_as_linked(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "specs").mkdir()
    (tmp_path / "specs" / "a.md").write_text("a\n")
    # specs/a.md 只在「被 ignore 的行」被連結
    (tmp_path / "MAP.md").write_text("intro\n[a](specs/a.md) <!-- doc-drift-ignore -->\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "c")
    base = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        capture_output=True, text=True,
    ).stdout.strip()
    fails, warns = engine.run_moc(tmp_path, base, "MAP.md", ("specs/",))
    assert fails == []
    assert not any("specs/a.md" in w for w in warns)  # 不應誤判 orphan


# codex #3：限定式引用指向 head 仍存在的同名異 scope symbol，不得 false-FAIL
def test_qualified_ref_to_kept_symbol_is_not_fail():
    removed = {("Python", "member", "A.B", "close")}
    head = {("Python", "member", "X.B", "close")}
    assert drift.classify_symbol_token("X.B.close", removed, head) is None
    # 真的被移除仍 FAIL
    assert drift.classify_symbol_token(
        "Foo.close",
        {("Python", "member", "Foo", "close")},
        {("Python", "member", "Bar", "close")},
    ) == "FAIL"


# codex #1：standalone doc-drift 對「本次移除的路徑引用」須 FAIL（不再只 WARN，對齊 R-22）
def test_run_doc_drift_fails_on_path_removed_this_change(tmp_path):
    _init(tmp_path)
    (tmp_path / "pkg").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "pkg" / "api.py").write_text("x = 1\n")
    (tmp_path / "docs" / "g.md").write_text("see [api](../pkg/api.py)\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "c")
    base = _head(tmp_path)
    (tmp_path / "pkg" / "api.py").unlink()  # 本次刪除被 doc 連結的路徑
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "rm")
    fails, _warns = engine.run_doc_drift(tmp_path, base)
    assert any("api.py" in f for f in fails)


# codex #2：base/head 物件無法供給時必須 fail-fast（raise），不得靜默放行
def test_run_doc_drift_fail_fast_on_unavailable_base(tmp_path):
    _init(tmp_path)
    (tmp_path / "a.py").write_text("x = 1\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "c")
    with pytest.raises(engine.DriftProvisionError):
        engine.run_doc_drift(tmp_path, "0" * 40)  # 不存在的 base 物件、無 remote 可 fetch


def test_cli_exit_2_on_unavailable_base(tmp_path):
    _init(tmp_path)
    (tmp_path / "a.py").write_text("x = 1\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "c")
    proc = subprocess.run(
        [sys.executable, "-m", "policy_check.doc_drift",
         "--repo", str(tmp_path), "--base", "0" * 40, "--head", "HEAD"],
        capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(REPO)},
    )
    assert proc.returncode == 2
    assert "ERROR" in proc.stderr


# codex #4：openspec change 孤兒判定為「目錄級」，proposal 已連結即不標 tasks.md
def test_openspec_change_orphans_dir_level():
    head = {"openspec/changes/foo/proposal.md", "openspec/changes/foo/tasks.md"}
    assert coverage.openspec_change_orphans(head, {"openspec/changes/foo/proposal.md"}) == []
    assert coverage.openspec_change_orphans(head, set()) == ["foo"]
