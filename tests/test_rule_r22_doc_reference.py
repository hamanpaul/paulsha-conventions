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


def test_r22_custom_doc_paths_are_scanned(tmp_path):
    # A repo-declared canonical doc outside README.md/docs/ must be scanned.
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text("doc_paths:\n  - GUIDE.md\n  - docs/**\n"))
    _write(tmp_path, "GUIDE.md", "see [gone](./missing_module.py)\n")
    _commit(tmp_path)
    res = get_rule().check(make_ctx(tmp_path))
    assert res.status == Status.WARN
    assert "missing_module.py" in res.detail


def test_r22_builtin_excludes_survive_wide_doc_paths(tmp_path):
    # Even if doc_paths matches everything, built-in noise trees stay excluded.
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text("doc_paths:\n  - '**'\n"))
    _write(tmp_path, "docs/superpowers/specs/x.md", "[future](./not_yet.py)\n")
    _write(tmp_path, "openspec/changes/y/proposal.md", "[future](./not_yet.py)\n")
    _commit(tmp_path)
    assert get_rule().check(make_ctx(tmp_path)).status == Status.PASS


def test_r22_path_removed_this_pr_is_fail(tmp_path):
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text())
    _write(tmp_path, "docs/guide.md", "see `policy_check/rules/r99_old.py`\n")
    _write(tmp_path, "policy_check/rules/r99_old.py", "x = 1\n")
    base = _commit(tmp_path, "base")            # r99_old.py 存在
    (tmp_path / "policy_check/rules/r99_old.py").unlink()
    _commit(tmp_path, "head")                   # 本次刪除
    res = get_rule().check(make_ctx(tmp_path, base=base))
    assert res.status == Status.FAIL
    assert "r99_old.py" in res.detail


def test_r22_preexisting_dangling_is_warn_even_with_base(tmp_path):
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text())
    _write(tmp_path, "docs/guide.md", "see `policy_check/rules/never.py`\n")
    base = _commit(tmp_path, "base")            # never.py 從未存在
    _write(tmp_path, "docs/guide.md", "see `policy_check/rules/never.py` (touch)\n")
    _commit(tmp_path, "head")
    res = get_rule().check(make_ctx(tmp_path, base=base))
    assert res.status == Status.WARN


def test_r22_symbol_removed_this_pr_is_fail(tmp_path):
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text())
    _write(tmp_path, "docs/api.md", "call `validate_wifi_llapi_case` to check\n")
    _write(tmp_path, "pkg/core.py", "def validate_wifi_llapi_case():\n    return 1\n")
    base = _commit(tmp_path, "base")
    (tmp_path / "pkg/core.py").write_text("def something_else():\n    return 1\n", encoding="utf-8")
    _commit(tmp_path, "head")                   # 本次移除該 def
    res = get_rule().check(make_ctx(tmp_path, base=base))
    assert res.status == Status.FAIL
    assert "validate_wifi_llapi_case" in res.detail


def test_r22_symbol_still_present_passes(tmp_path):
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text())
    _write(tmp_path, "docs/api.md", "call `validate_wifi_llapi_case`\n")
    _write(tmp_path, "pkg/core.py", "def validate_wifi_llapi_case():\n    return 1\n")
    base = _commit(tmp_path, "base")
    _write(tmp_path, "docs/api.md", "call `validate_wifi_llapi_case` now\n")
    _commit(tmp_path, "head")
    assert get_rule().check(make_ctx(tmp_path, base=base)).status == Status.PASS


def test_r22_symbol_prong_off_without_base(tmp_path):
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text())
    _write(tmp_path, "docs/api.md", "call `ghost_symbol_xyz`\n")
    _commit(tmp_path)
    # 無 base：symbol prong 關閉，且無懸空路徑 → PASS
    assert get_rule().check(make_ctx(tmp_path)).status == Status.PASS


def test_r22_unresolvable_base_degrades_to_warn(tmp_path):
    # base ref 無法解析（如 CI 傳入壞的 base）→ 等同無 base：路徑降 WARN、symbol prong 關閉、不崩
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text())
    _write(tmp_path, "docs/g.md", "see `missing_thing.py`\n")
    _commit(tmp_path)
    res = get_rule().check(make_ctx(tmp_path, base="no-such-ref-xyz"))
    assert res.status == Status.WARN


def test_r22_upstream_divergence_not_attributed_as_new_break(tmp_path):
    # base 落後分支：main 才有的檔、分支沒有、doc 引用它 → 應 WARN（非本次刪除），不可 FAIL。
    # 以 merge-base 對齊兩條 prong 的歸責基準後此案例為 WARN（two-dot base-tip 會誤判 FAIL）。
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text())
    _write(tmp_path, "docs/g.md", "see `mod_only_on_main.py`\n")
    c0 = _commit(tmp_path, "c0")                       # merge-base：該檔不存在
    _git(tmp_path, "checkout", "-q", "-b", "mainref")
    _write(tmp_path, "mod_only_on_main.py", "x = 1\n")
    _commit(tmp_path, "main adds mod")                 # mainref tip 有該檔
    _git(tmp_path, "checkout", "-q", "-b", "feature", c0)  # HEAD 回到 c0（無該檔）
    res = get_rule().check(make_ctx(tmp_path, base="mainref"))
    assert res.status == Status.WARN


def test_r22_directory_ref_not_flagged(tmp_path):
    # 反引號裡的目錄（無副檔名）不應被當成本地檔懸空
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text())
    _write(tmp_path, "README.md", "tests live under `tests/`\n")
    _commit(tmp_path)
    assert get_rule().check(make_ctx(tmp_path)).status == Status.PASS


def test_r22_github_org_repo_slug_not_flagged(tmp_path):
    # GitHub org/repo slug（含 / 但非本地檔）不應誤報
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text())
    _write(tmp_path, "README.md", "uses `hamanpaul/paulsha-conventions` engine\n")
    _commit(tmp_path)
    assert get_rule().check(make_ctx(tmp_path)).status == Status.PASS


def test_r22_qualified_ref_to_removed_member_fails(tmp_path):
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text())
    _write(tmp_path, "pkg/m.py", "class Foo:\n    def close(self):\n        pass\n"
                                  "class Bar:\n    def close(self):\n        pass\n")
    _write(tmp_path, "docs/g.md", "use `Bar.close`\n")
    base = _commit(tmp_path)
    # 移除 Foo.close（保留 Bar.close），doc 改引用 Foo.close
    _write(tmp_path, "pkg/m.py", "class Foo:\n    pass\n"
                                  "class Bar:\n    def close(self):\n        pass\n")
    _write(tmp_path, "docs/g.md", "use `Foo.close`\n")
    _commit(tmp_path)
    res = get_rule().check(make_ctx(tmp_path, base=base))
    assert res.status == Status.FAIL


def test_r22_bare_ref_partial_removal_warns(tmp_path):
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text())
    _write(tmp_path, "pkg/m.py", "class Foo:\n    def close(self):\n        pass\n"
                                  "class Bar:\n    def close(self):\n        pass\n")
    _write(tmp_path, "docs/g.md", "use `close`\n")
    base = _commit(tmp_path)
    _write(tmp_path, "pkg/m.py", "class Foo:\n    pass\n"
                                  "class Bar:\n    def close(self):\n        pass\n")
    _commit(tmp_path)
    res = get_rule().check(make_ctx(tmp_path, base=base))
    assert res.status == Status.WARN
