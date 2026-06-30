"""對 #25 code-review findings 的回歸測試（symbols/exempt/coverage/engine 硬化）。"""
import subprocess
from pathlib import Path

from policy_check.doc_drift import coverage, engine, exempt, symbols


def _git(repo: Path, *a):
    subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)


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
