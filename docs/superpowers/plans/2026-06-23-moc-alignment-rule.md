# MOC-alignment 規則（R-24）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 R-24（moc-alignment）：repo 宣告 `moc` 後，盯其靜態脈絡檔與動態連結地圖有沒有跟本次變更同步（靜態鮮度 WARN／連結懸空 diff-aware FAIL-WARN／連結孤兒 WARN）。

**Architecture:** 先把 R-22 與 R-24 共用的 doc-link helper 抽到 `policy_check/rules/_doc_links.py`（DRY，免跨 rule 引私有），R-22 改用它；再實作 R-24 三瓣，全部只吃 `ctx.changed_files` + `ctx.repo_root` + git（platform-agnostic）。R-08 擴充驗 `moc`。

**Tech Stack:** Python 3.12、pytest、規則 plugin（`@register` 依 `rNN_` 自動載入）、`git`（diff-aware 用 subprocess）。

**Branch:** `feature/moc-alignment-rule`（已開）。對應 openspec change `moc-alignment-rule`、設計文件 `docs/superpowers/specs/2026-06-23-moc-alignment-rule-design.md`。

---

## File Structure

- `policy_check/rules/_doc_links.py` — **新建**：共用 helper `LINK_RE` / `looks_like_path` / `path_candidates` / `git_tracked` / `resolve_base`（自 r22 抽出）。
- `policy_check/rules/r22_doc_reference.py` — **改**：改 import 上述 helper，移除本地重複定義（行為不變）。
- `policy_check/rules/r08_policy_config_schema.py` — **改**：驗 `moc`。
- `policy_check/rules/r24_moc_alignment.py` — **新建**：R-24 規則。
- `tests/test_doc_links.py` — **新建**：helper 單元測試。
- `tests/test_rule_r08_policy_config_schema.py` — **改**：`moc` schema 測試。
- `tests/test_rule_r24_moc_alignment.py` — **新建**。
- `tests/test_rules_presence.py` — **改**：R-24 註冊。
- `CLAUDE.md` / `README.md` / `CHANGELOG.md` — **改**。

---

## Task 1: 抽出共用 doc-link helper（DRY 重構）

**Files:**
- Create: `policy_check/rules/_doc_links.py`
- Modify: `policy_check/rules/r22_doc_reference.py`
- Test: `tests/test_doc_links.py`

- [ ] **Step 1: 寫 helper 單元測試（先建檔，會因模組不存在而 fail）**

建立 `tests/test_doc_links.py`：

```python
from __future__ import annotations

from policy_check.rules._doc_links import looks_like_path, path_candidates, LINK_RE


def test_looks_like_path_accepts_code_ext_and_dotslash():
    assert looks_like_path("docs/x.md")
    assert looks_like_path("./LICENSE.md")
    assert not looks_like_path("feature/<slug>")
    assert not looks_like_path("hamanpaul/paulsha-conventions")  # org/repo slug, no ext


def test_path_candidates_normalizes_doc_relative_and_root():
    cands = path_candidates("docs/MOC.md", "plans/x.md")
    assert "docs/plans/x.md" in cands
    assert "plans/x.md" in cands


def test_link_re_extracts_markdown_target():
    assert LINK_RE.findall("see [x](docs/a.md) and [y](b.md)") == ["docs/a.md", "b.md"]
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python3 -m pytest tests/test_doc_links.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'policy_check.rules._doc_links'`

- [ ] **Step 3: 建立 `_doc_links.py`（內容自 r22 原樣搬出）**

建立 `policy_check/rules/_doc_links.py`：

```python
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
_CODE_EXTS = (".py", ".sh", ".yml", ".yaml", ".toml", ".js", ".ts",
              ".json", ".cfg", ".ini", ".md")


def looks_like_path(tok: str) -> bool:
    tok = tok.strip()
    if not tok or " " in tok or any(c in tok for c in "<>{}*$"):
        return False
    if tok.startswith(("./", "../")):
        return True
    return tok.endswith(_CODE_EXTS)


def path_candidates(doc_rel: str, target: str) -> list[str]:
    target = target.split("#", 1)[0].strip()
    if not target or target.startswith(("http://", "https://", "mailto:")):
        return []
    doc_dir = Path(doc_rel).parent
    cands: list[str] = []
    for base in (doc_dir / target, Path(target)):
        norm = os.path.normpath(base.as_posix())
        if norm == "." or norm.startswith("..") or norm.startswith("/"):
            continue
        posix = Path(norm).as_posix()
        if posix not in cands:
            cands.append(posix)
    return cands


def git_tracked(root: Path, rev: str | None = None) -> set[str]:
    cmd = ["git", "-C", str(root)]
    cmd += (["ls-tree", "-r", "--name-only", rev] if rev else ["ls-files"])
    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return set()
    return {l.strip() for l in out.splitlines() if l.strip()}


def resolve_base(root: Path, base_ref: str | None) -> str | None:
    if not base_ref:
        return None
    for cand in (base_ref, f"origin/{base_ref}"):
        try:
            sha = subprocess.check_output(
                ["git", "-C", str(root), "rev-parse", "--verify", "-q", f"{cand}^{{commit}}"],
                text=True, stderr=subprocess.DEVNULL).strip()
        except subprocess.CalledProcessError:
            continue
        if not sha:
            continue
        try:
            mb = subprocess.check_output(
                ["git", "-C", str(root), "merge-base", sha, "HEAD"],
                text=True, stderr=subprocess.DEVNULL).strip()
        except subprocess.CalledProcessError:
            mb = ""
        return mb or sha
    return None
```

- [ ] **Step 4: 跑 helper 測試確認通過**

Run: `python3 -m pytest tests/test_doc_links.py -q`
Expected: PASS

- [ ] **Step 5: 把 r22 改用共用 helper（移除本地重複）**

在 `policy_check/rules/r22_doc_reference.py`：刪除本地 `_LINK_RE`、`_looks_like_path`、`_path_candidates`、`_git_tracked`、`_resolve_base` 五個定義與其用到的 `_CODE_EXTS`、`os`/`subprocess` import（若不再使用），改為：

```python
from policy_check.rules._doc_links import (
    LINK_RE as _LINK_RE,
    looks_like_path as _looks_like_path,
    path_candidates as _path_candidates,
    git_tracked as _git_tracked,
    resolve_base as _resolve_base,
)
```

保留 r22 的 symbol-prong 專屬碼（`_CODE_SPAN_RE`、`_SNAKE_RE`、`_CAMEL_RE`、`_DEFCLASS_RE`、`_is_symbol`、`_defined_in_head`、`_removed_symbols`、`_in_scope`、`_is_exempt`、`_extract_refs`）。`re` 仍需保留（symbol 用）。

- [ ] **Step 6: 跑 r22 既有測試確認零回歸**

Run: `python3 -m pytest tests/test_rule_r22_doc_reference.py tests/test_self_dogfood_r16.py -q`
Expected: PASS（r22 行為不變）

- [ ] **Step 7: Commit**

```bash
git add policy_check/rules/_doc_links.py policy_check/rules/r22_doc_reference.py tests/test_doc_links.py
git commit -m "refactor(doc-links): 抽出 r22/r24 共用 link helper 至 _doc_links"
```

---

## Task 2: R-08 驗證 moc 區塊

**Files:**
- Modify: `policy_check/rules/r08_policy_config_schema.py`
- Test: `tests/test_rule_r08_policy_config_schema.py`

- [ ] **Step 1: 寫失敗測試**

加到 `tests/test_rule_r08_policy_config_schema.py`（沿用既有 `_write_config` / `_r08` / `_ctx` helper）：

```python
def test_r08_fail_on_moc_triggers_not_list(tmp_path):
    repo = _write_config(tmp_path, "policy_profile: flat\npolicy_version: 1.0.0\nmoc:\n  triggers: \"Dockerfile\"\n")
    result = _r08().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "moc.triggers" in result.message


def test_r08_fail_on_moc_static_not_str(tmp_path):
    repo = _write_config(tmp_path, "policy_profile: flat\npolicy_version: 1.0.0\nmoc:\n  static: [a, b]\n")
    result = _r08().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "moc.static" in result.message


def test_r08_pass_on_valid_moc(tmp_path):
    repo = _write_config(tmp_path, "policy_profile: flat\npolicy_version: 1.0.0\nmoc:\n  static: docs/ctx.yml\n  map: docs/MOC.md\n  triggers: [\"Dockerfile*\"]\n")
    result = _r08().check(_ctx(repo))
    assert result.status == Status.PASS
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python3 -m pytest tests/test_rule_r08_policy_config_schema.py -q -k moc`
Expected: FAIL（驗證未實作，invalid 案例誤判 PASS）

- [ ] **Step 3: 實作 moc 驗證**

在 `policy_check/rules/r08_policy_config_schema.py` 的 `check()` 內、`conventions_engine` 區塊之後、`return ... PASS` 之前插入：

```python
        # 驗證 moc 區塊：mapping；static/map 為 str；triggers 為 list[str]
        moc = data.get("moc")
        if moc is not None:
            if not isinstance(moc, dict):
                return RuleResult(rule_id=self.rule_id, status=Status.FAIL,
                                  message="moc must be a mapping")
            for key in ("static", "map"):
                val = moc.get(key)
                if val is not None and not isinstance(val, str):
                    return RuleResult(rule_id=self.rule_id, status=Status.FAIL,
                                      message=f"moc.{key} must be a string")
            triggers = moc.get("triggers")
            if triggers is not None and (
                not isinstance(triggers, list) or not all(isinstance(x, str) for x in triggers)
            ):
                return RuleResult(rule_id=self.rule_id, status=Status.FAIL,
                                  message="moc.triggers must be a list of strings")
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python3 -m pytest tests/test_rule_r08_policy_config_schema.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add policy_check/rules/r08_policy_config_schema.py tests/test_rule_r08_policy_config_schema.py
git commit -m "feat(r08): 驗證 moc.static / moc.map / moc.triggers"
```

---

## Task 3: R-24 骨架（NA / 豁免）

**Files:**
- Create: `policy_check/rules/r24_moc_alignment.py`
- Test: `tests/test_rule_r24_moc_alignment.py`

- [ ] **Step 1: 寫失敗測試（含 git repo helper）**

建立 `tests/test_rule_r24_moc_alignment.py`：

```python
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
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python3 -m pytest tests/test_rule_r24_moc_alignment.py -q`
Expected: FAIL with `AssertionError: R-24 ... not registered` (KeyError)

- [ ] **Step 3: 建立 R-24 骨架**

建立 `policy_check/rules/r24_moc_alignment.py`：

```python
from __future__ import annotations

from fnmatch import fnmatch

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register
from policy_check.rules._doc_links import (
    LINK_RE, path_candidates, git_tracked, resolve_base,
)

_GOVERNED_PREFIXES = ("openspec/changes/", "docs/superpowers/")


@register
class R24MocAlignment:
    rule_id = "R-24"
    exempt_label = "policy-exempt:moc-alignment"

    def check(self, ctx: RuleContext) -> RuleResult:
        if self.exempt_label in ctx.pr_labels:
            return RuleResult(self.rule_id, Status.SKIP,
                              f"Skipped by exemption label: {self.exempt_label}.",
                              exempt_label=self.exempt_label)

        moc = (ctx.config or {}).get("moc") or {}
        if not isinstance(moc, dict) or not moc:
            return RuleResult(self.rule_id, Status.PASS, "No moc declared; R-24 not applicable.")

        fails: list[str] = []
        warns: list[str] = []
        # prongs filled in later tasks
        return self._verdict(fails, warns)

    def _verdict(self, fails, warns) -> RuleResult:
        if fails:
            return RuleResult(self.rule_id, Status.FAIL,
                              f"MOC map has {len(fails)} dangling reference(s) introduced by this change.",
                              detail="\n".join(fails[:20]))
        if warns:
            return RuleResult(self.rule_id, Status.WARN,
                              f"MOC alignment: {len(warns)} advisory item(s).",
                              detail="\n".join(warns[:20]))
        return RuleResult(self.rule_id, Status.PASS, "MOC aligned with this change.")
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python3 -m pytest tests/test_rule_r24_moc_alignment.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add policy_check/rules/r24_moc_alignment.py tests/test_rule_r24_moc_alignment.py
git commit -m "feat(r24): moc-alignment 骨架（NA / 豁免 / verdict 彙整）"
```

---

## Task 4: 靜態鮮度瓣（WARN）

**Files:**
- Modify: `policy_check/rules/r24_moc_alignment.py`
- Test: `tests/test_rule_r24_moc_alignment.py`

- [ ] **Step 1: 寫失敗測試**

加到 `tests/test_rule_r24_moc_alignment.py`：

```python
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
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python3 -m pytest tests/test_rule_r24_moc_alignment.py -q -k "trigger or static"`
Expected: FAIL（鮮度瓣未實作，第一個 case 回 PASS）

- [ ] **Step 3: 實作鮮度瓣**

在 `r24_moc_alignment.py` 的 `check()` 內，`fails`/`warns` 宣告之後、`return self._verdict(...)` 之前插入：

```python
        changed = set(ctx.changed_files or [])
        static = moc.get("static")
        triggers = moc.get("triggers") or []
        if static and triggers and changed:
            hit = sorted(f for f in changed if any(fnmatch(f, g) for g in triggers))
            if hit and static not in changed:
                warns.append(
                    f"static MOC '{static}' 未隨 trigger 變更同步；命中：{', '.join(hit[:5])}"
                )
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python3 -m pytest tests/test_rule_r24_moc_alignment.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add policy_check/rules/r24_moc_alignment.py tests/test_rule_r24_moc_alignment.py
git commit -m "feat(r24): 靜態鮮度瓣（trigger 變但 static 未同步 → WARN）"
```

---

## Task 5: 動態連結懸空瓣（diff-aware FAIL/WARN）

**Files:**
- Modify: `policy_check/rules/r24_moc_alignment.py`
- Test: `tests/test_rule_r24_moc_alignment.py`

- [ ] **Step 1: 寫失敗測試**

加到 `tests/test_rule_r24_moc_alignment.py`（懸空需 base/head 兩 commit）：

```python
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
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python3 -m pytest tests/test_rule_r24_moc_alignment.py -q -k dangling`
Expected: FAIL（懸空瓣未實作）

- [ ] **Step 3: 實作懸空瓣 + map ref 抽取**

在 `r24_moc_alignment.py`：先加類別方法 `_map_refs`（放在 `check` 之後）：

```python
    @staticmethod
    def _map_refs(map_rel: str, text: str):
        """yield (token, candidates)：僅取指向受治理產物的連結。"""
        seen: set[str] = set()
        for m in LINK_RE.finditer(text):
            tok = m.group(1)
            cands = [c for c in path_candidates(map_rel, tok)
                     if c.startswith(_GOVERNED_PREFIXES)]
            if cands and tok not in seen:
                seen.add(tok)
                yield tok, cands
```

再在 `check()` 的鮮度瓣之後、`return self._verdict(...)` 之前插入：

```python
        map_rel = moc.get("map")
        root = ctx.repo_root
        head_files = git_tracked(root)
        if map_rel and map_rel in head_files:
            try:
                text = (root / map_rel).read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
            base = resolve_base(root, ctx.pr_base_ref)
            base_files = git_tracked(root, base) if base else set()
            for token, cands in self._map_refs(map_rel, text):
                if any(c in head_files for c in cands):
                    continue
                if base and any(c in base_files for c in cands):
                    fails.append(f"{map_rel} -> {token}（本次移除）")
                else:
                    warns.append(f"{map_rel} -> {token}")
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python3 -m pytest tests/test_rule_r24_moc_alignment.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add policy_check/rules/r24_moc_alignment.py tests/test_rule_r24_moc_alignment.py
git commit -m "feat(r24): 動態連結懸空瓣（diff-aware：本次破壞 FAIL、陳年 WARN）"
```

---

## Task 6: 動態連結孤兒瓣（WARN，永不 FAIL）

**Files:**
- Modify: `policy_check/rules/r24_moc_alignment.py`
- Test: `tests/test_rule_r24_moc_alignment.py`

- [ ] **Step 1: 寫失敗測試**

加到 `tests/test_rule_r24_moc_alignment.py`：

```python
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
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python3 -m pytest tests/test_rule_r24_moc_alignment.py -q -k orphan`
Expected: FAIL（孤兒瓣未實作，第一個 case 回 PASS）

- [ ] **Step 3: 實作孤兒瓣**

在 `r24_moc_alignment.py` 的懸空瓣區塊內（`for token, cands ...` 迴圈之後、仍在 `if map_rel and map_rel in head_files:` 區塊裡）插入：

```python
            linked = {c for _t, cs in self._map_refs(map_rel, text) for c in cs}
            # plans / specs：精確檔路徑須被 link
            for rel in sorted(head_files):
                if rel.endswith(".md") and rel.startswith(
                    ("docs/superpowers/plans/", "docs/superpowers/specs/")
                ) and rel not in linked:
                    warns.append(f"孤兒：{rel} 未被 {map_rel} 連結")
            # active openspec changes：change dir 下任一連結即算
            change_names = sorted({
                rel.split("/")[2] for rel in head_files
                if rel.startswith("openspec/changes/")
                and not rel.startswith("openspec/changes/archive/")
                and len(rel.split("/")) >= 3
            })
            for name in change_names:
                prefix = f"openspec/changes/{name}/"
                if not any(t.startswith(prefix) for t in linked):
                    warns.append(f"孤兒：openspec change '{name}' 未被 {map_rel} 連結")
```

- [ ] **Step 4: 跑測試確認通過（且確認孤兒永不 FAIL）**

Run: `python3 -m pytest tests/test_rule_r24_moc_alignment.py -q`
Expected: PASS（孤兒只進 `warns`，不可能 FAIL）

- [ ] **Step 5: Commit**

```bash
git add policy_check/rules/r24_moc_alignment.py tests/test_rule_r24_moc_alignment.py
git commit -m "feat(r24): 動態連結孤兒瓣（plans/specs/changes 未連結 → WARN）"
```

---

## Task 7: R-24 註冊存在性測試

**Files:**
- Modify: `tests/test_rules_presence.py`

- [ ] **Step 1: 寫測試**

加到 `tests/test_rules_presence.py`：

```python
def test_r24_is_registered():
    rule = get_rule("R-24")
    assert rule.rule_id == "R-24"
    assert rule.exempt_label == "policy-exempt:moc-alignment"
```

- [ ] **Step 2: 跑測試確認通過**

Run: `python3 -m pytest tests/test_rules_presence.py -q -k r24`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_rules_presence.py
git commit -m "test(r24): 註冊存在性"
```

---

## Task 8: 慣例檔 / README / CHANGELOG

**Files:**
- Modify: `CLAUDE.md`, `README.md`, `CHANGELOG.md`

- [ ] **Step 1: CLAUDE.md**

1. 「完成任務（claim done）前」清單在 R-23 條後新增：
   `- [ ] R-24：repo 宣告 `moc` 時，本次變更已同步靜態脈絡（`moc.static`）與動態地圖（`moc.map` 無懸空、新產物已連結），或上 `policy-exempt:moc-alignment``
2. Exemption 白名單在 `engine-pin` 後新增：
   `- `policy-exempt:moc-alignment` — R-24 MOC 與本次變更對齊`
3. 「Doc-alignment review」段末新增一句：
   `MOC 的**狀態語意對齊**（stage 宣稱 done 是否真 done）同屬此 advisory 層：R-24 只確定性檢查連結/鮮度，狀態是否真對齊由 Copilot reviewer 留言提醒。`

- [ ] **Step 2: README.md 規則總覽**

在 R-23 列後新增：
```
| R-24 | MOC 與本次變更對齊 | repo 宣告 `moc` 時：`moc.triggers` 命中但 `moc.static` 未同步（WARN）／`moc.map` 連結懸空（本次新破壞 FAIL、陳年 WARN）／active openspec change・plan・spec 未被連結（WARN） | `policy-exempt:moc-alignment` |
```
並把標題 `## 規則總覽（R-01 ~ R-23）` 改為 `（R-01 ~ R-24）`。

- [ ] **Step 3: CHANGELOG [Unreleased]**

在 `### Added` 頂端新增：
```markdown
- **新增 R-24（moc-alignment）**：repo 於 `.paul-project.yml` 宣告 `moc`（`static` / `map` / `triggers`）後生效（未宣告 → NA）。三瓣：靜態鮮度（trigger 變但 `moc.static` 未同步 → WARN）／動態連結懸空（`moc.map` 連到不存在產物，本次新破壞 FAIL、陳年 WARN）／動態連結孤兒（active openspec change・`docs/superpowers/{plans,specs}` 未被連結 → WARN，永不 FAIL）。platform-agnostic（純 git-level）。豁免 `policy-exempt:moc-alignment`。R-08 擴充驗 `moc`。
```

- [ ] **Step 4: 驗證 + Commit**

Run: `python3 -m pytest -q && python3 -m policy_check --repo .`
Expected: pytest 全綠；policy_check 無 failure（本 repo 未宣告 `moc` → R-24 NA）

```bash
git add CLAUDE.md README.md CHANGELOG.md
git commit -m "docs: 慣例檔/README/CHANGELOG 補 R-24（moc-alignment）"
```

---

## Task 9: 自我 dogfood（本 repo 宣告 moc）

**Files:**
- Modify: `.paul-project.yml`
- Create: `docs/MOC.md`

- [ ] **Step 1: 建立本 repo 的 MOC 地圖**

建立 `docs/MOC.md`，link 到現有 active openspec change 與 plans/specs（避免孤兒 WARN）：

```markdown
# paulsha-conventions MOC

## Active changes
- [moc-alignment-rule](../openspec/changes/moc-alignment-rule/proposal.md)

## Plans / Specs
- [moc plan](superpowers/plans/2026-06-23-moc-alignment-rule.md)
- [moc design](superpowers/specs/2026-06-23-moc-alignment-rule-design.md)
- [agent-files design](superpowers/specs/2026-06-23-agent-files-single-source-and-version-attestation-design.md)
- [agent-files plan](superpowers/plans/2026-06-23-agent-files-single-source-and-version-attestation.md)
```

- [ ] **Step 2: `.paul-project.yml` 宣告 moc（本 repo 無 build trigger，省 triggers/static）**

在 `.paul-project.yml` 末尾加：
```yaml
moc:
  map: docs/MOC.md
```

- [ ] **Step 3: dogfood 驗證**

Run: `python3 -m policy_check --repo . --only R-24`
Expected: R-24 PASS 或僅少量孤兒 WARN（若有未 link 的舊 plan/spec，補進 `docs/MOC.md` 直到 PASS）

- [ ] **Step 4: 確認 R-22 對 docs/MOC.md 無新懸空**

Run: `python3 -m policy_check --repo . --only R-22`
Expected: 無「本次新破壞」FAIL

- [ ] **Step 5: Commit**

```bash
git add .paul-project.yml docs/MOC.md
git commit -m "chore(r24): 本 repo 自宣告 moc 並建立 docs/MOC.md（dogfood）"
```

---

## Task 10: 最終驗證

- [ ] **Step 1: 全套件**

Run: `python3 -m pytest -q`
Expected: 全綠

- [ ] **Step 2: 完整 policy_check**

Run: `python3 -m policy_check --repo .`
Expected: 無 failure

- [ ] **Step 3: 勾 openspec tasks + validate**

```bash
sed -i 's/^- \[ \]/- [x]/' openspec/changes/moc-alignment-rule/tasks.md
openspec validate "moc-alignment-rule"
git add openspec/changes/moc-alignment-rule/tasks.md
git commit -m "chore(openspec): 勾選 moc-alignment-rule tasks"
```

---

## Release 待辦（merge 當下）

merge 當下 PATCH bump `1.0.6 → 1.0.7`（`flat`，一個 feature batch）：`VERSION` / `policy_version` / canonical `CLAUDE.md`（`managed-by@v1.0.7`）/ workflow `policy_version` / tag `v1.0.7` / `RELEASES.md`。PR：zh-tw、release-branch 上 `policy-exempt:branch-name`（版號含點）、`release:1.0.7` label。

## Self-Review

**Spec coverage（對照 openspec specs）：**
- moc schema（R-08）→ Task 2。NA → Task 3。靜態鮮度 → Task 4。連結懸空 diff-aware → Task 5。連結孤兒（plans/specs/changes，WARN）→ Task 6。豁免 → Task 3。platform-agnostic（只用 changed_files/repo_root/git）→ 全程未讀任何 GitHub/GitLab env。

**Placeholder scan：** 無 TBD/TODO；每個 code step 有實際程式碼與預期輸出。

**Type consistency：** `_doc_links` 的 `LINK_RE`/`looks_like_path`/`path_candidates`/`git_tracked`/`resolve_base` 在 r22（aliased）、r24、tests 一致；R-24 的 `_map_refs`/`_verdict`、`exempt_label="policy-exempt:moc-alignment"`、`_GOVERNED_PREFIXES` 前後一致；`ctx.changed_files`/`ctx.pr_base_ref`/`ctx.config["moc"]` 與 `RuleContext` 欄位一致。
