# R-22 Doc-Alignment Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增確定性引擎規則 R-22，偵測 `README.md`/`docs/**` 對 code 產物的「結構化懸空引用」，並補上三層治理（Tier 1 checklist、Tier 3 review 導引）與 `doc_reference` 設定／R-08 schema。

**Architecture:** 單一偵測器，兩條 prong——Prong P（路徑/連結，doc-driven 快照）、Prong S（symbol，diff-driven）。`base..head` diff 用來分級：本次新破壞 FAIL、陳年 WARN；無 base 時 Prong P 降 WARN、Prong S 關閉。複用 R-21 的 git/self-exempt 風格。

**Tech Stack:** Python 3.12、`subprocess`+git、`re`、`fnmatch`、pytest（temp git repo fixtures）。

完整設計：`docs/superpowers/specs/2026-06-18-r22-doc-alignment-governance-design.md`；契約：`openspec/changes/r22-doc-alignment-governance/specs/doc-reference/spec.md`。

---

## File Structure

- Create `policy_check/rules/r22_doc_reference.py` — R-22 規則（偵測器 + 兩 prong + diff seam）。
- Create `tests/test_rule_r22_doc_reference.py` — TDD 測試（temp git repo）。
- Modify `policy_check/rules/r08_policy_config_schema.py` — 驗 `doc_reference.allow` 為 `list[str]`。
- Modify `tests/test_rule_r08_policy_config_schema.py` — R-08 新增測試。
- Modify `.paul-project.yml` — 新增 `doc_reference.allow`（dogfood）。
- Modify `CLAUDE.md` / `AGENTS.md` / `GEMINI.md` / `.github/copilot-instructions.md` — Tier 1/3 + merge-bump convention（四份**逐字一致**）。
- Modify `README.md` — 規則表 + 豁免清單 + 三層治理段。
- Modify `CHANGELOG.md` — `[Unreleased]` entry。

## Test helper（放在 `tests/test_rule_r22_doc_reference.py` 頂部，供各測試共用）

```python
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
```

---

## Task 1: R-22 Prong P — 快照懸空（無 diff → WARN）、排除、豁免、註冊

**Files:**
- Create: `policy_check/rules/r22_doc_reference.py`
- Test: `tests/test_rule_r22_doc_reference.py`

- [ ] **Step 1: 寫失敗測試（clean PASS、懸空連結 WARN、排除、豁免、allow）**

在 helper 之後加：

```python
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
```

- [ ] **Step 2: 跑測試確認 RED**

Run: `python3 -m pytest tests/test_rule_r22_doc_reference.py -q`
Expected: FAIL — `AssertionError: R-22 is not registered`（規則尚未存在）。

- [ ] **Step 3: 實作 `policy_check/rules/r22_doc_reference.py`（快照版）**

```python
from __future__ import annotations

import os
import re
import subprocess
from fnmatch import fnmatch
from pathlib import Path

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register

_IN_SCOPE_PREFIXES = ("docs/",)           # 加上 README.md（見 _in_scope）
_EXCLUDE_PREFIXES = ("openspec/", "docs/superpowers/", "tests/fixtures/doc-reference/")
_SELF_EXEMPT = (
    "policy_check/rules/r22_doc_reference.py",
    "tests/test_rule_r22_doc_reference.py",
    "tests/fixtures/doc-reference/**",
)
_CODE_EXTS = (".py", ".sh", ".yml", ".yaml", ".toml", ".js", ".ts",
              ".json", ".cfg", ".ini", ".md")

_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
_CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")
_SNAKE_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$")
_CAMEL_RE = re.compile(r"^[A-Za-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*$")
_DEFCLASS_RE = re.compile(r"^([+-])\s*(?:async\s+)?(?:def|class)\s+([A-Za-z_]\w*)")


def _in_scope(rel: str) -> bool:
    if rel.startswith(_EXCLUDE_PREFIXES):
        return False
    return rel == "README.md" or rel.startswith(_IN_SCOPE_PREFIXES)


def _is_exempt(rel: str, allow: list[str]) -> bool:
    for pat in (*_SELF_EXEMPT, *allow):
        if fnmatch(rel, pat):
            return True
        base = pat[:-3] if pat.endswith("/**") else pat
        if rel == base or rel.startswith(base.rstrip("/") + "/"):
            return True
    return False


def _is_symbol(tok: str) -> bool:
    return len(tok) >= 3 and bool(_SNAKE_RE.match(tok) or _CAMEL_RE.match(tok))


def _looks_like_path(tok: str) -> bool:
    tok = tok.strip()
    if not tok or " " in tok or any(c in tok for c in "<>{}*$"):
        return False  # 排除 placeholder/glob（如 feature/<slug>、${{ inputs.x }}）
    return "/" in tok or tok.endswith(_CODE_EXTS)


def _git_tracked(root: Path, rev: str | None = None) -> set[str]:
    cmd = ["git", "-C", str(root)]
    cmd += (["ls-tree", "-r", "--name-only", rev] if rev else ["ls-files"])
    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return set()
    return {l.strip() for l in out.splitlines() if l.strip()}


def _path_candidates(doc_rel: str, target: str) -> list[str]:
    """正規化成 repo-relative posix 候選（doc-relative 與 root-relative 各一）。"""
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


def _extract_refs(doc_rel: str, text: str):
    """yield (kind, token, payload)。kind=='path' → payload=list[str] 候選；'symbol' → payload=name。"""
    for m in _LINK_RE.finditer(text):
        cands = _path_candidates(doc_rel, m.group(1))
        if cands:
            yield ("path", m.group(1), cands)
    for m in _CODE_SPAN_RE.finditer(text):
        tok = m.group(1).strip()
        if _looks_like_path(tok):
            cands = _path_candidates(doc_rel, tok)
            if cands:
                yield ("path", tok, cands)
        elif _is_symbol(tok):
            yield ("symbol", tok, tok)


@register
class R22DocReference:
    rule_id = "R-22"
    exempt_label = "policy-exempt:doc-reference"

    def check(self, ctx: RuleContext) -> RuleResult:
        if self.exempt_label in ctx.pr_labels:
            return RuleResult(self.rule_id, Status.SKIP,
                              f"Skipped by exemption label: {self.exempt_label}.",
                              exempt_label=self.exempt_label)

        root = ctx.repo_root
        config = ctx.config or {}
        allow = (config.get("doc_reference") or {}).get("allow", [])
        head_files = _git_tracked(root)

        fails: list[str] = []
        warns: list[str] = []
        for rel in sorted(head_files):
            if not _in_scope(rel) or _is_exempt(rel, allow):
                continue
            try:
                text = (root / rel).read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for kind, token, payload in _extract_refs(rel, text):
                if kind == "path" and not any(c in head_files for c in payload):
                    warns.append(f"{rel} -> {token}")   # Task 2 會把新破壞升 FAIL

        if fails:
            return RuleResult(self.rule_id, Status.FAIL,
                              f"docs contain {len(fails)} dangling reference(s) introduced by this change.",
                              detail="\n".join(fails[:20]))
        if warns:
            return RuleResult(self.rule_id, Status.WARN,
                              f"docs contain {len(warns)} pre-existing dangling reference(s) (advisory).",
                              detail="\n".join(warns[:20]))
        return RuleResult(self.rule_id, Status.PASS, "No dangling doc references detected.")
```

- [ ] **Step 4: 跑測試確認 GREEN**

Run: `python3 -m pytest tests/test_rule_r22_doc_reference.py -q`
Expected: PASS（6 個測試）。

- [ ] **Step 5: Commit**

```bash
git add policy_check/rules/r22_doc_reference.py tests/test_rule_r22_doc_reference.py
git commit -m "feat(r22): doc-reference Prong P 快照懸空偵測（WARN）+ 排除/豁免"
```

---

## Task 2: Prong P diff 分級（新破壞 FAIL、陳年 WARN）

**Files:**
- Modify: `policy_check/rules/r22_doc_reference.py`
- Test: `tests/test_rule_r22_doc_reference.py`

- [ ] **Step 1: 寫失敗測試**

```python
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
```

- [ ] **Step 2: 跑測試確認 RED**

Run: `python3 -m pytest tests/test_rule_r22_doc_reference.py -k "removed_this_pr or preexisting" -q`
Expected: FAIL — 第一個應為 FAIL 卻得 WARN（diff 分級尚未實作）。

- [ ] **Step 3: 加入 diff seam 與分級**

在 module 加入 base 解析與 base 檔案集合：

```python
def _resolve_base(root: Path, base_ref: str | None) -> str | None:
    if not base_ref:
        return None
    for cand in (base_ref, f"origin/{base_ref}"):
        try:
            sha = subprocess.check_output(
                ["git", "-C", str(root), "rev-parse", "--verify", "-q", f"{cand}^{{commit}}"],
                text=True, stderr=subprocess.DEVNULL).strip()
        except subprocess.CalledProcessError:
            continue
        if sha:
            return sha
    return None
```

把 `check()` 主迴圈前加：

```python
        base = _resolve_base(root, ctx.pr_base_ref)
        base_files = _git_tracked(root, base) if base else set()
```

把 Prong P 命中處改成分級：

```python
                if kind == "path" and not any(c in head_files for c in payload):
                    if base and any(c in base_files for c in payload):
                        fails.append(f"{rel} -> {token} (removed this change)")
                    else:
                        warns.append(f"{rel} -> {token}")
```

- [ ] **Step 4: 跑測試確認 GREEN**

Run: `python3 -m pytest tests/test_rule_r22_doc_reference.py -q`
Expected: PASS（全部）。

- [ ] **Step 5: Commit**

```bash
git add policy_check/rules/r22_doc_reference.py tests/test_rule_r22_doc_reference.py
git commit -m "feat(r22): Prong P diff 分級（本次刪除 FAIL、陳年 WARN）"
```

---

## Task 3: Prong S — diff 驅動 symbol（本次移除的 def/class）

**Files:**
- Modify: `policy_check/rules/r22_doc_reference.py`
- Test: `tests/test_rule_r22_doc_reference.py`

- [ ] **Step 1: 寫失敗測試**

```python
def test_r22_symbol_removed_this_pr_is_fail(tmp_path):
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text())
    _write(tmp_path, "docs/api.md", "call `validate_wifi_llapi_case` to check\n")
    _write(tmp_path, "core.py", "def validate_wifi_llapi_case():\n    return 1\n")
    base = _commit(tmp_path, "base")
    (tmp_path / "core.py").write_text("def something_else():\n    return 1\n", encoding="utf-8")
    _commit(tmp_path, "head")                   # 本次移除該 def
    res = get_rule().check(make_ctx(tmp_path, base=base))
    assert res.status == Status.FAIL
    assert "validate_wifi_llapi_case" in res.detail


def test_r22_symbol_still_present_passes(tmp_path):
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text())
    _write(tmp_path, "docs/api.md", "call `validate_wifi_llapi_case`\n")
    _write(tmp_path, "core.py", "def validate_wifi_llapi_case():\n    return 1\n")
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
```

- [ ] **Step 2: 跑測試確認 RED**

Run: `python3 -m pytest tests/test_rule_r22_doc_reference.py -k symbol -q`
Expected: FAIL — `symbol_removed_this_pr` 得 PASS（Prong S 未實作）。

- [ ] **Step 3: 實作 Prong S helpers + 接進 check()**

```python
def _removed_symbols(root: Path, base: str) -> set[str]:
    try:
        diff = subprocess.check_output(
            ["git", "-C", str(root), "diff", f"{base}...HEAD", "--", "*.py"],
            text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return set()
    candidates: set[str] = set()
    for line in diff.splitlines():
        m = _DEFCLASS_RE.match(line)
        if m and m.group(1) == "-":
            candidates.add(m.group(2))
    return {name for name in candidates if not _defined_in_head(root, name)}


def _defined_in_head(root: Path, name: str) -> bool:
    try:
        subprocess.check_output(
            ["git", "-C", str(root), "grep", "-qE",
             rf"(def|class)[[:space:]]+{re.escape(name)}\b", "HEAD"],
            stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False
```

在 `check()` 算出 `base` 後加：

```python
        removed_syms = _removed_symbols(root, base) if base else set()
```

在主迴圈的 ref 處理補 symbol 分支：

```python
                elif kind == "symbol" and payload in removed_syms:
                    fails.append(f"{rel} -> `{payload}` (def/class removed this change)")
```

- [ ] **Step 4: 跑測試確認 GREEN**

Run: `python3 -m pytest tests/test_rule_r22_doc_reference.py -q`
Expected: PASS（全部）。

- [ ] **Step 5: Commit**

```bash
git add policy_check/rules/r22_doc_reference.py tests/test_rule_r22_doc_reference.py
git commit -m "feat(r22): Prong S diff 驅動 symbol 懸空（本次移除 def/class → FAIL）"
```

---

## Task 4: R-08 schema — `doc_reference.allow` 為 list[str]

**Files:**
- Modify: `policy_check/rules/r08_policy_config_schema.py`
- Test: `tests/test_rule_r08_policy_config_schema.py`

- [ ] **Step 1: 寫失敗測試（沿用既有測試風格）**

在 `tests/test_rule_r08_policy_config_schema.py` 加：

```python
def test_r08_fail_when_doc_reference_allow_not_list(tmp_path):
    (tmp_path / ".paul-project.yml").write_text(
        "policy_profile: flat\npolicy_version: 1.0.4\n"
        "doc_reference:\n  allow: \"docs/legacy\"\n", encoding="utf-8")
    from tests.test_rule_r08_policy_config_schema import _get_rule  # 既有 helper（或仿 R-21 寫法）
    res = _get_rule().check(RuleContext(repo_root=tmp_path, profile="flat",
                                        policy_version="1.0.4", config={}))
    assert res.status == Status.FAIL
    assert "doc_reference.allow" in res.message


def test_r08_pass_when_doc_reference_allow_is_list(tmp_path):
    (tmp_path / ".paul-project.yml").write_text(
        "policy_profile: flat\npolicy_version: 1.0.4\n"
        "doc_reference:\n  allow: [\"docs/legacy/**\"]\n", encoding="utf-8")
    res = _get_rule().check(RuleContext(repo_root=tmp_path, profile="flat",
                                        policy_version="1.0.4", config={}))
    assert res.status == Status.PASS
```

> 註：若該測試檔尚無 `_get_rule`/import，依檔內既有 pattern 補（比照 R-21 測試的 `get_rule()`）。

- [ ] **Step 2: 跑測試確認 RED**

Run: `python3 -m pytest tests/test_rule_r08_policy_config_schema.py -k doc_reference -q`
Expected: FAIL — 非 list 仍 PASS（驗證未加）。

- [ ] **Step 3: 在 `r08_policy_config_schema.py` 的 secret_scan 驗證之後加入**

```python
        doc_reference = data.get("doc_reference")
        if doc_reference is not None:
            if not isinstance(doc_reference, dict):
                return RuleResult(
                    rule_id=self.rule_id, status=Status.FAIL,
                    message="doc_reference must be a mapping")
            allow = doc_reference.get("allow")
            if allow is not None and (
                not isinstance(allow, list) or not all(isinstance(x, str) for x in allow)
            ):
                return RuleResult(
                    rule_id=self.rule_id, status=Status.FAIL,
                    message="doc_reference.allow must be a list of strings")
```

- [ ] **Step 4: 跑測試確認 GREEN**

Run: `python3 -m pytest tests/test_rule_r08_policy_config_schema.py -q`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add policy_check/rules/r08_policy_config_schema.py tests/test_rule_r08_policy_config_schema.py
git commit -m "feat(r08): 驗證 doc_reference.allow 為 list[str]"
```

---

## Task 5: `.paul-project.yml` dogfood

**Files:**
- Modify: `.paul-project.yml`

- [ ] **Step 1: 加入 doc_reference 區塊**

在現有 `secret_scan:` 區塊後加（self-exempt 已涵蓋 fixtures/規則檔，這裡僅備逃生閥；先放空 allow，跑全套後若有合法懸空再補）：

```yaml
doc_reference:
  allow: []
```

- [ ] **Step 2: 跑全套確認自身 PASS/WARN（非 FAIL）**

Run: `python3 -m policy_check --repo . --only R-22`
Expected: R-22 為 pass 或 warn（不得 fail）。若 fail，把該合法引用加入 `doc_reference.allow` 或修正 docs。

- [ ] **Step 3: Commit**

```bash
git add .paul-project.yml
git commit -m "chore(r22): .paul-project.yml 加入 doc_reference dogfood 設定"
```

---

## Task 6: Tier 1 / Tier 3 — 四份 agent 慣例檔（逐字一致）

**Files:**
- Modify: `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.github/copilot-instructions.md`

- [ ] **Step 1: 對四份檔做相同三處編輯**

1. 「改 code 時」段加一行：
   `- [ ] 評估 R-22：搬移/改名/刪除 code 產物（檔案、def/class）時，同步更新 README.md / docs/** 中引用它的段落；無法即時處理上 policy-exempt:doc-reference 並附理由`
2. 「完成任務（claim done）前」段加一行：
   `- [ ] R-22：docs 對本次刪改產物的引用無懸空（CI 報新破壞會 FAIL、陳年 WARN），或上 policy-exempt:doc-reference`
3. 「改版號時（release 觸發時）」段加一行（merge-bump convention）：
   `- [ ] 若本 PR 將版本 bump 延後（feature 先進 [Unreleased]），merge 當下必須立即補做對應 release bump（VERSION / policy_version / 四份 agent 檔 / managed-by / tag / RELEASES.md），不得留置`
4. 「Exemption Labels 白名單」段加一行：
   `- \`policy-exempt:doc-reference\` — R-22 文件懸空引用`
5. 新增一段（四份相同）：
   ```markdown
   ## Doc-alignment review（PR review 時）
   review 變更時，除了 R-22 抓得到的懸空引用，另留意語意陳舊：引用都還在、但 docs 描述了已被這次變更改掉的架構/行為；發現時於 PR 留言指出、建議作者更新。Advisory，不擋 merge。
   ```

- [ ] **Step 2: 驗四份逐字一致 + R-13/R-14 綠**

Run: `diff <(sed -n '/Agent Policy Checklist/,$p' CLAUDE.md) <(sed -n '/Agent Policy Checklist/,$p' AGENTS.md)` （預期無差異；GEMINI.md 同理）
Run: `python3 -m policy_check --repo . --only R-13,R-14`
Expected: 兩條 pass。

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md AGENTS.md GEMINI.md .github/copilot-instructions.md
git commit -m "docs(conventions): R-22 checklist/白名單/review 導引 + merge 立即 bump convention（四份同步）"
```

---

## Task 7: README — 規則表 + 豁免清單 + 三層治理段

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 編輯三處**

1. 規則總覽表加列：`| R-22 | doc-reference 懸空引用（README/docs 對 code 產物的路徑/連結/symbol；新破壞 FAIL、陳年 WARN）| policy-exempt:doc-reference |`（欄位對齊既有表）。
2. 豁免 label 清單加 `policy-exempt:doc-reference`。
3. 新增段：
   ```markdown
   ## Doc-alignment governance（三層）
   - Tier 1（預防）：agent 改 code 時同步更新引用該產物的 docs（見 agent 慣例檔 checklist）。
   - Tier 2（確定性 gate）：R-22 在 CI 偵測 README/docs 的結構化懸空引用——本次新破壞 FAIL、陳年 WARN。
   - Tier 3（語意複審）：建議將 GitHub Copilot 設為 PR reviewer，複審「引用仍在但描述過時」的語意陳舊。
   ```

- [ ] **Step 2: 確認 R-16/R-18 等不受影響**

Run: `python3 -m policy_check --repo . --only R-02,R-16,R-18`
Expected: pass（README 段落/結構未破壞）。

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(readme): 加入 R-22 規則表/豁免/三層 doc-alignment governance 段"
```

---

## Task 8: CHANGELOG + 全套驗證

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: `[Unreleased]` 加 entry**

在 `## [Unreleased]` 下的 `### Added` 加：
```markdown
- **新增 R-22（doc-reference 懸空引用）**：偵測 README.md/docs/** 對 code 產物（路徑、markdown 內部連結、反引號 symbol）的結構化懸空引用；本次變更新破壞 FAIL、陳年懸空 WARN、無 diff context（本地）Prong P 降 WARN/Prong S 關閉；排除 openspec/**、docs/superpowers/** 與自身 fixtures；`.paul-project.yml` 新增 `doc_reference.allow`、R-08 驗其型別；豁免 label `policy-exempt:doc-reference`。同步 Tier 1 checklist 與 Tier 3 review 導引（四份 agent 檔），新增「defer 的版本 bump 須於 merge 當下立即補做」convention。（policy_version 1.0.4 → 1.0.5，merge 當下 bump）
```

- [ ] **Step 2: 全套測試 + policy self-dogfood**

Run: `python3 -m pytest -q`
Expected: all pass（含新 R-22/R-08 測試）。
Run: `python3 -m policy_check --repo .`
Expected: `- fail: 0`（R-22 自身 pass 或 warn，不得 fail）。

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): R-22 doc-alignment governance 進 [Unreleased]"
```

---

## Post-implementation（非本 PR 步驟，列出供 finishing 階段參考）

- requesting-code-review → 修正 → re-review。
- openspec archive：`openspec archive r22-doc-alignment-governance`。
- PR：`Closes #11`，body 載明「merge 當下立即執行 1.0.5 release bump（VERSION/policy_version/四份檔/tag/RELEASES.md）」。
- **merge 當下**：執行 1.0.5 release bump（依 Task 6 step 1.3 寫入的 convention）。
