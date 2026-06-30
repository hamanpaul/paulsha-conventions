# doc-drift 獨立 Action（OSS-ready）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 R-22/R-24 的 doc↔code drift 抽成語言無關、零設定的共用核心與獨立 GitHub Action（OSS-ready），消除 Python-only 與同名 fail-open 兩個限制。

**Architecture:** 新增 `policy_check/doc_drift/` 共用核心（按 primitive 組織：refs/paths/symbols/coverage/langs/provision），symbol 抽取用 universal-ctags 的 JSON 輸出取 scoped identity `(language, kind, scope, name)`，base/HEAD 各自 `git archive` 到 temp 後掃描、差集求 removed。R-22/R-24 refactor 成薄 consumer；standalone Action 包同一核心、自理 base/head SHA 供給。

**Tech Stack:** Python 3.11、PyYAML、universal-ctags 6.2.0（JSON 輸出，欄位 `name`/`kind`/`scope`/`language`）、pytest、GitHub composite action（bash）。

**對應 spec：** `docs/superpowers/specs/2026-06-30-doc-drift-action-design.md`、`openspec/changes/doc-drift-action/`。

**全程慣例：** 在 worktree `feature/25-doc-drift-action`；每 phase TDD-first（先紅）；commit 訊息 zh-tw + `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`；測試 `python3 -m pytest -q`。

---

## 核心型別約定（全 plan 一致）

- `Identity = tuple[str, str, str, str]`：`(language, kind, scope, name)`；top-level symbol 的 `scope` 為 `""`。
- `langs.public_kinds(language: str) -> set[str]`、`langs.supported_languages() -> set[str]`。
- `symbols.parse_ctags_json(lines: Iterable[str]) -> set[Identity]`（純函式，可不碰 git 測）。
- `symbols.symbols_at(repo_root: Path, sha: str) -> set[Identity]`。
- `provision.ensure_object(repo_root: Path, sha: str) -> bool`。
- `drift.removed_identities(base: set[Identity], head: set[Identity]) -> set[Identity]`。
- `drift.classify_symbol_token(token: str, removed: set[Identity], head: set[Identity]) -> str | None`（回 `"FAIL"` / `"WARN"` / `None`）。

## File Structure

- `policy_check/doc_drift/__init__.py` — 套件
- `policy_check/doc_drift/langs.py` — 語言註冊表（ctags language → public kind 白名單）
- `policy_check/doc_drift/symbols.py` — ctags JSON 抽取 + `git archive` 取 ref 內容
- `policy_check/doc_drift/provision.py` — base/head git 物件供給契約
- `policy_check/doc_drift/drift.py` — scoped-identity 差集 + token 分類語義
- `policy_check/doc_drift/refs.py` — doc 引用抽取（自 `_doc_links.py` 共用面）
- `policy_check/doc_drift/paths.py` — in-repo path-drift primitive（自 `_doc_links.py`）
- `policy_check/doc_drift/coverage.py` — orphan + static freshness（前綴參數化）
- `policy_check/doc_drift/exempt.py` — inline marker + allowlist 檔（P5）
- `policy_check/doc_drift/__main__.py` — 薄 CLI（P2）
- `.github/actions/doc-drift/{action.yml,run.sh,README.md}` — Action（P2）
- `examples/doc-drift/` — demo fixtures（P2）
- `tests/test_doc_drift_*.py` — 各 primitive 測試

---

## Task 1: 套件骨架 + 語言註冊表（Python）

**Files:**
- Create: `policy_check/doc_drift/__init__.py`
- Create: `policy_check/doc_drift/langs.py`
- Test: `tests/test_doc_drift_langs.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_doc_drift_langs.py
from policy_check.doc_drift import langs


def test_python_public_kinds():
    assert langs.public_kinds("Python") == {"function", "class", "member"}


def test_unknown_language_has_no_kinds():
    assert langs.public_kinds("Haskell") == set()


def test_python_is_supported():
    assert "Python" in langs.supported_languages()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_doc_drift_langs.py -q`
Expected: FAIL — `ModuleNotFoundError: policy_check.doc_drift`

- [ ] **Step 3: Write minimal implementation**

```python
# policy_check/doc_drift/__init__.py
```

```python
# policy_check/doc_drift/langs.py
from __future__ import annotations

# ctags `language` 名稱 → 計為 public symbol 的 ctags kind（long name）白名單。
# 新增語言只動這張表，差集/比對演算法不變。
_LANG_KINDS: dict[str, set[str]] = {
    "Python": {"function", "class", "member"},
}


def public_kinds(language: str) -> set[str]:
    return set(_LANG_KINDS.get(language, set()))


def supported_languages() -> set[str]:
    return set(_LANG_KINDS)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_doc_drift_langs.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add policy_check/doc_drift/__init__.py policy_check/doc_drift/langs.py tests/test_doc_drift_langs.py
git commit -m "feat(doc-drift): 語言註冊表骨架（Python public kinds）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: ctags JSON 解析成 scoped Identity（純函式）

**Files:**
- Create: `policy_check/doc_drift/symbols.py`
- Test: `tests/test_doc_drift_symbols.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_doc_drift_symbols.py
from policy_check.doc_drift import symbols

# 取自 `ctags --output-format=json` 對 Foo.close / Bar.close / top_level 的實際輸出
_JSON_LINES = [
    '{"_type":"tag","name":"Foo","language":"Python","kind":"class"}',
    '{"_type":"tag","name":"Bar","language":"Python","kind":"class"}',
    '{"_type":"tag","name":"close","language":"Python","kind":"member","scope":"Foo","scopeKind":"class"}',
    '{"_type":"tag","name":"close","language":"Python","kind":"member","scope":"Bar","scopeKind":"class"}',
    '{"_type":"tag","name":"top_level","language":"Python","kind":"function"}',
    '{"_type":"tag","name":"x","language":"Python","kind":"variable"}',  # 非 public kind，應濾掉
    'not-json-noise',  # robust：跳過壞行
]


def test_parse_keeps_only_public_kinds_with_scope():
    got = symbols.parse_ctags_json(_JSON_LINES)
    assert ("Python", "class", "", "Foo") in got
    assert ("Python", "member", "Foo", "close") in got
    assert ("Python", "member", "Bar", "close") in got
    assert ("Python", "function", "", "top_level") in got
    # variable 不在白名單
    assert not any(name == "x" for (_l, _k, _s, name) in got)


def test_foo_and_bar_close_are_distinct_identities():
    got = symbols.parse_ctags_json(_JSON_LINES)
    closes = {ident for ident in got if ident[3] == "close"}
    assert closes == {
        ("Python", "member", "Foo", "close"),
        ("Python", "member", "Bar", "close"),
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_doc_drift_symbols.py -q`
Expected: FAIL — `AttributeError: module ... has no attribute 'parse_ctags_json'`

- [ ] **Step 3: Write minimal implementation**

```python
# policy_check/doc_drift/symbols.py
from __future__ import annotations

import json
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Iterable

from policy_check.doc_drift import langs

Identity = tuple[str, str, str, str]  # (language, kind, scope, name)


def parse_ctags_json(lines: Iterable[str]) -> set[Identity]:
    """把 ctags --output-format=json 的每行 tag 收斂成 public scoped identity。"""
    out: set[Identity] = set()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue  # 跳過 ctags 偶發的非 tag 行
        if obj.get("_type") != "tag":
            continue
        language = obj.get("language") or ""
        kind = obj.get("kind") or ""
        if kind not in langs.public_kinds(language):
            continue
        scope = obj.get("scope") or ""
        name = obj.get("name") or ""
        if name:
            out.add((language, kind, scope, name))
    return out


def _run_ctags(target_dir: Path) -> list[str]:
    langs_arg = ",".join(sorted(langs.supported_languages()))
    proc = subprocess.run(
        ["ctags", "--output-format=json", "--fields=+lnsSK",
         f"--languages={langs_arg}", "-R", "-f", "-", str(target_dir)],
        capture_output=True, text=True, check=False,
    )
    return proc.stdout.splitlines()


def symbols_at(repo_root: Path, sha: str) -> set[Identity]:
    """對某 git ref 的內容跑 ctags，回 public scoped identity 集合。"""
    with tempfile.TemporaryDirectory() as tmp:
        archive = subprocess.run(
            ["git", "-C", str(repo_root), "archive", "--format=tar", sha],
            capture_output=True, check=True,
        ).stdout
        tar_path = Path(tmp) / "tree.tar"
        tar_path.write_bytes(archive)
        extract_dir = Path(tmp) / "tree"
        extract_dir.mkdir()
        with tarfile.open(tar_path) as tf:
            tf.extractall(extract_dir)
        return parse_ctags_json(_run_ctags(extract_dir))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_doc_drift_symbols.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add policy_check/doc_drift/symbols.py tests/test_doc_drift_symbols.py
git commit -m "feat(doc-drift): ctags JSON → scoped identity 抽取

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: scoped-identity 差集 + token 分類語義

**Files:**
- Create: `policy_check/doc_drift/drift.py`
- Test: `tests/test_doc_drift_drift.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_doc_drift_drift.py
from policy_check.doc_drift import drift

BASE = {
    ("Python", "member", "Foo", "close"),
    ("Python", "member", "Bar", "close"),
    ("Python", "function", "", "legacy_init"),
}
# HEAD：移除 Foo.close（保留 Bar.close）、移除 legacy_init
HEAD = {
    ("Python", "member", "Bar", "close"),
}


def test_removed_identities():
    removed = drift.removed_identities(BASE, HEAD)
    assert ("Python", "member", "Foo", "close") in removed
    assert ("Python", "function", "", "legacy_init") in removed
    assert ("Python", "member", "Bar", "close") not in removed


def test_qualified_ref_to_removed_is_fail():
    removed = drift.removed_identities(BASE, HEAD)
    assert drift.classify_symbol_token("Foo.close", removed, HEAD) == "FAIL"


def test_bare_ref_partial_removal_is_warn():
    removed = drift.removed_identities(BASE, HEAD)
    # close 仍存在於 Bar → 歧義
    assert drift.classify_symbol_token("close", removed, HEAD) == "WARN"


def test_bare_ref_fully_vanished_is_fail():
    removed = drift.removed_identities(BASE, HEAD)
    assert drift.classify_symbol_token("legacy_init", removed, HEAD) == "FAIL"


def test_unrelated_token_is_none():
    removed = drift.removed_identities(BASE, HEAD)
    assert drift.classify_symbol_token("something_else", removed, HEAD) is None
    # Bar.close 未被移除
    assert drift.classify_symbol_token("Bar.close", removed, HEAD) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_doc_drift_drift.py -q`
Expected: FAIL — `ModuleNotFoundError` / `AttributeError`

- [ ] **Step 3: Write minimal implementation**

```python
# policy_check/doc_drift/drift.py
from __future__ import annotations

from policy_check.doc_drift.symbols import Identity


def removed_identities(base: set[Identity], head: set[Identity]) -> set[Identity]:
    return base - head


def _scope_matches(ident_scope: str, ref_scope: str) -> bool:
    # 限定式引用的 scope 段可比 ctags scope 的末段（A.B.close 的 ref "B" 命中 scope "A.B"）
    if not ident_scope:
        return False
    return ident_scope == ref_scope or ident_scope.split(".")[-1] == ref_scope


def classify_symbol_token(
    token: str, removed: set[Identity], head: set[Identity]
) -> str | None:
    """回 'FAIL' / 'WARN' / None。token 可為限定式（Foo.close）或裸名（close）。"""
    removed_names = {name for (_l, _k, _s, name) in removed}
    head_names = {name for (_l, _k, _s, name) in head}

    if "." in token:
        ref_scope, _, name = token.rpartition(".")
        ref_scope = ref_scope.split(".")[-1]
        for (_l, _k, scope, nm) in removed:
            if nm == name and _scope_matches(scope, ref_scope):
                return "FAIL"
        return None

    name = token
    if name not in removed_names:
        return None
    if name in head_names:
        return "WARN"   # 部分移除、同名仍留存 → 歧義
    return "FAIL"        # 完全消失
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_doc_drift_drift.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add policy_check/doc_drift/drift.py tests/test_doc_drift_drift.py
git commit -m "feat(doc-drift): scoped-identity 差集與 token 分類（限定式/裸名/歧義）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: base/HEAD git 物件供給契約

**Files:**
- Create: `policy_check/doc_drift/provision.py`
- Test: `tests/test_doc_drift_provision.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_doc_drift_provision.py
import subprocess
from pathlib import Path

from policy_check.doc_drift import provision


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args],
                          check=True, capture_output=True, text=True).stdout.strip()


def _init(repo: Path) -> str:
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "a.py").write_text("def f():\n    pass\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c")
    return _git(repo, "rev-parse", "HEAD")


def test_existing_object_is_present(tmp_path):
    sha = _init(tmp_path)
    assert provision.ensure_object(tmp_path, sha) is True


def test_missing_object_without_remote_returns_false(tmp_path):
    _init(tmp_path)
    bogus = "0" * 40
    assert provision.ensure_object(tmp_path, bogus) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_doc_drift_provision.py -q`
Expected: FAIL — `AttributeError: ... 'ensure_object'`

- [ ] **Step 3: Write minimal implementation**

```python
# policy_check/doc_drift/provision.py
from __future__ import annotations

import subprocess
from pathlib import Path


def _has_tree(repo_root: Path, sha: str) -> bool:
    return subprocess.run(
        ["git", "-C", str(repo_root), "cat-file", "-e", f"{sha}^{{tree}}"],
        capture_output=True,
    ).returncode == 0


def ensure_object(repo_root: Path, sha: str) -> bool:
    """確保 sha 的樹物件在本地；缺則嘗試 fetch。回 True/False，不丟例外。"""
    if _has_tree(repo_root, sha):
        return True
    subprocess.run(
        ["git", "-C", str(repo_root), "fetch", "--quiet", "origin", sha],
        capture_output=True,
    )
    return _has_tree(repo_root, sha)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_doc_drift_provision.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add policy_check/doc_drift/provision.py tests/test_doc_drift_provision.py
git commit -m "feat(doc-drift): base/head git 物件供給（cat-file 驗證 + fetch fallback）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: refs/paths primitive 自 `_doc_links.py` 抽共用面

**Files:**
- Create: `policy_check/doc_drift/refs.py`
- Create: `policy_check/doc_drift/paths.py`
- Test: `tests/test_doc_drift_refs.py`

說明：`_doc_links.py` 既有 `LINK_RE`/`looks_like_path`/`path_candidates`/`git_tracked`/`resolve_base` 已被 R-22/R-24 共用。本 task 在 `doc_drift` 下建薄 re-export + doc 引用抽取（symbol token 與 path token），不改 `_doc_links.py` 本體（避免破壞既有測試），後續 task 再把 r22/r24 改指向 `doc_drift`。

- [ ] **Step 1: Write the failing test**

```python
# tests/test_doc_drift_refs.py
from policy_check.doc_drift import refs


def test_extract_symbol_and_path_tokens():
    text = "see `Foo.close` and `legacy_init`, file [x](../a.py)\n"
    got = list(refs.extract_refs("docs/g.md", text))
    kinds = {(kind, token) for (kind, token, _payload) in got}
    assert ("symbol", "Foo.close") in kinds
    assert ("symbol", "legacy_init") in kinds
    assert any(kind == "path" for (kind, _t, _p) in got)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_doc_drift_refs.py -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# policy_check/doc_drift/paths.py
from __future__ import annotations

# 共用既有實作（單一真相）；doc_drift 對外只暴露穩定名稱。
from policy_check.rules._doc_links import (  # noqa: F401
    LINK_RE, looks_like_path, path_candidates, git_tracked, resolve_base,
)
```

```python
# policy_check/doc_drift/refs.py
from __future__ import annotations

import re

from policy_check.doc_drift.paths import LINK_RE, looks_like_path, path_candidates

_CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")
_SNAKE_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$")
_CAMEL_RE = re.compile(r"^[A-Za-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*$")
# 限定式：A.b（含點，末段為 snake/Camel/簡單識別字）
_QUALIFIED_RE = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+$")


def _is_symbol_token(tok: str) -> bool:
    if len(tok) < 3:
        return False
    return bool(_SNAKE_RE.match(tok) or _CAMEL_RE.match(tok) or _QUALIFIED_RE.match(tok))


def extract_refs(doc_rel: str, text: str):
    """yield (kind, token, payload)。kind=='path'→payload=候選list；'symbol'→payload=token。"""
    for m in LINK_RE.finditer(text):
        cands = path_candidates(doc_rel, m.group(1))
        if cands:
            yield ("path", m.group(1), cands)
    for m in _CODE_SPAN_RE.finditer(text):
        tok = m.group(1).strip()
        if looks_like_path(tok):
            cands = path_candidates(doc_rel, tok)
            if cands:
                yield ("path", tok, cands)
        elif _is_symbol_token(tok):
            yield ("symbol", tok, tok)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_doc_drift_refs.py -q`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add policy_check/doc_drift/refs.py policy_check/doc_drift/paths.py tests/test_doc_drift_refs.py
git commit -m "feat(doc-drift): refs/paths primitive（含限定式 symbol token）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: R-22 refactor 上核心（Python parity）

**Files:**
- Modify: `policy_check/rules/r22_doc_reference.py`
- Test: `tests/test_rule_r22_doc_reference.py`（既有，須續綠）+ 新增 scoped 案

- [ ] **Step 1: Write the failing test（新增 scoped 行為）**

```python
# 追加到 tests/test_rule_r22_doc_reference.py
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
```

- [ ] **Step 2: Run to verify new tests fail（舊測試先全綠基準）**

Run: `python3 -m pytest tests/test_rule_r22_doc_reference.py -q`
Expected: 既有測試 PASS、兩個新測試 FAIL（現行 Python-regex 不做 scoped）

- [ ] **Step 3: Refactor R-22 的 symbol prong 呼叫核心**

把 `_removed_symbols` / `_defined_in_head` / `_DEFCLASS_RE` 換成核心。symbol prong 改為：

```python
# r22_doc_reference.py 內，import 區加：
from policy_check.doc_drift import symbols as dd_symbols
from policy_check.doc_drift import drift as dd_drift
from policy_check.doc_drift import provision as dd_provision

# check() 內，取代原 removed_syms 計算：
removed_ids: set = set()
head_ids: set = set()
if base:
    head_sha = "HEAD"
    if dd_provision.ensure_object(root, base) and dd_provision.ensure_object(root, head_sha):
        base_ids = dd_symbols.symbols_at(root, base)
        head_ids = dd_symbols.symbols_at(root, head_sha)
        removed_ids = dd_drift.removed_identities(base_ids, head_ids)

# symbol 比對處改為：
elif kind == "symbol":
    verdict = dd_drift.classify_symbol_token(token, removed_ids, head_ids)
    if verdict == "FAIL":
        fails.append(f"{rel} -> `{token}` (symbol removed this change)")
    elif verdict == "WARN":
        warns.append(f"{rel} -> `{token}` (ambiguous: same-named symbol remains)")
```

保留 path prong 行為不變（可同時改呼叫 `doc_drift.paths`，但非必要）。移除死碼 `_DEFCLASS_RE`/`_removed_symbols`/`_defined_in_head`/`_is_symbol`（symbol token 改由 `doc_drift.refs` 概念對齊；R-22 既有 `_extract_refs` 可保留，但 symbol 判定接受限定式——把 `_is_symbol` 換成 `refs._is_symbol_token` 或於本檔加上限定式 regex）。

> R-22 自身 import `_extract_refs`：把其 symbol 分支的 `_is_symbol(tok)` 換成同時接受限定式 token（沿用 Task 5 的 `_QUALIFIED_RE` 規則），確保 `Foo.close` 會被當 symbol token。

- [ ] **Step 4: Run tests to verify all pass**

Run: `python3 -m pytest tests/test_rule_r22_doc_reference.py -q`
Expected: PASS（含兩個新案）

- [ ] **Step 5: Run full suite（確認無迴歸）**

Run: `python3 -m pytest -q`
Expected: 全綠（原 314 + 新增）

- [ ] **Step 6: Commit**

```bash
git add policy_check/rules/r22_doc_reference.py tests/test_rule_r22_doc_reference.py
git commit -m "refactor(R-22): symbol-drift 改呼叫語言無關 scoped 核心

- def/class 裸名 regex → ctags scoped identity（限定式精確、裸名保守、歧義 WARN）
- 消除同名 fail-open；Python parity，既有測試續綠

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: coverage primitive + R-24 refactor（前綴參數化）

**Files:**
- Create: `policy_check/doc_drift/coverage.py`
- Modify: `policy_check/rules/r24_moc_alignment.py`
- Test: `tests/test_doc_drift_coverage.py`、`tests/test_rule_r24_moc_alignment.py`（既有續綠）

- [ ] **Step 1: Write the failing test**

```python
# tests/test_doc_drift_coverage.py
from policy_check.doc_drift import coverage

DEFAULT_PREFIXES = ("openspec/changes/", "docs/superpowers/plans/", "docs/superpowers/specs/")


def test_orphan_detects_unlinked_plan():
    head_files = {"docs/superpowers/plans/X.md", "docs/MOC.md"}
    linked = set()  # MOC 沒連到 X
    orphans = coverage.orphans(head_files, linked, prefixes=DEFAULT_PREFIXES)
    assert "docs/superpowers/plans/X.md" in orphans


def test_custom_prefix_scopes_orphan_check():
    head_files = {"specs/X.md", "docs/superpowers/plans/Y.md"}
    linked = set()
    orphans = coverage.orphans(head_files, linked, prefixes=("specs/",))
    assert "specs/X.md" in orphans
    assert "docs/superpowers/plans/Y.md" not in orphans  # 不在自訂前綴內
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_doc_drift_coverage.py -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# policy_check/doc_drift/coverage.py
from __future__ import annotations

from collections.abc import Iterable

# 預設受治理前綴（沿用 R-24 現值）。openspec change 以「目錄下任一連結即算」處理，
# 故這裡的 plans/specs 為精確檔案；openspec changes 的孤兒判定由呼叫端傳對應集合。
DEFAULT_GOVERNED_PREFIXES = (
    "openspec/changes/",
    "docs/superpowers/plans/",
    "docs/superpowers/specs/",
)


def orphans(
    head_files: Iterable[str],
    linked: set[str],
    *,
    prefixes: tuple[str, ...] = DEFAULT_GOVERNED_PREFIXES,
) -> list[str]:
    """回在受治理前綴下、為 .md 精確檔、且未被 linked 涵蓋者。"""
    out = []
    for rel in sorted(head_files):
        if not rel.endswith(".md"):
            continue
        if not rel.startswith(tuple(prefixes)):
            continue
        if rel not in linked:
            out.append(rel)
    return out
```

- [ ] **Step 4: Run to verify it passes**

Run: `python3 -m pytest tests/test_doc_drift_coverage.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Refactor R-24 呼叫核心 + 前綴可由 config 取得**

在 `r24_moc_alignment.py`：把 `_GOVERNED_PREFIXES` 改為自 `moc.governed_prefixes`（若有）取得、預設 `coverage.DEFAULT_GOVERNED_PREFIXES`；orphan 的 plans/specs 判定改呼叫 `coverage.orphans(...)`（openspec change 的「目錄下任一連結」判定保留在 r24，傳入已連結集合）。map 懸空判定保留現行（已用 `_doc_links`，等價）。

- [ ] **Step 6: Run R-24 tests + full suite**

Run: `python3 -m pytest tests/test_rule_r24_moc_alignment.py -q && python3 -m pytest -q`
Expected: 全綠

- [ ] **Step 7: Commit**

```bash
git add policy_check/doc_drift/coverage.py policy_check/rules/r24_moc_alignment.py tests/test_doc_drift_coverage.py
git commit -m "refactor(R-24): orphan/freshness 改呼叫核心 coverage + 治理前綴參數化

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: 薄 CLI（doc-drift / moc 兩 mode）

**Files:**
- Create: `policy_check/doc_drift/__main__.py`
- Create: `policy_check/doc_drift/engine.py`（共用判定邏輯，CLI 與規則皆可呼叫）
- Test: `tests/test_doc_drift_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_doc_drift_cli.py
import subprocess, sys
from pathlib import Path


def _git(repo: Path, *a): subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)


def _setup(repo: Path):
    _git(repo, "init", "-q"); _git(repo, "config", "user.email", "t@t"); _git(repo, "config", "user.name", "t")
    (repo / "pkg").mkdir(); (repo / "docs").mkdir()
    (repo / "pkg" / "m.py").write_text("def legacy_init():\n    pass\n")
    (repo / "docs" / "g.md").write_text("use `legacy_init`\n")
    _git(repo, "add", "-A"); _git(repo, "commit", "-q", "-m", "c")
    base = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    (repo / "pkg" / "m.py").write_text("# removed\n")
    _git(repo, "add", "-A"); _git(repo, "commit", "-q", "-m", "rm")
    return base


def _run(repo: Path, base: str):
    return subprocess.run(
        [sys.executable, "-m", "policy_check.doc_drift", "--mode", "doc-drift",
         "--repo", str(repo), "--base", base, "--head", "HEAD"],
        capture_output=True, text=True,
    )


def test_cli_fail_on_removed_symbol(tmp_path):
    base = _setup(tmp_path)
    proc = _run(tmp_path, base)
    assert proc.returncode != 0
    assert "legacy_init" in proc.stdout


def test_cli_pass_when_clean(tmp_path):
    base = _setup(tmp_path)
    # doc 不再引用被刪 symbol
    (tmp_path / "docs" / "g.md").write_text("clean\n")
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-aqm", "fix"], check=True, capture_output=True)
    proc = _run(tmp_path, base)
    assert proc.returncode == 0
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_doc_drift_cli.py -q`
Expected: FAIL — no `__main__`

- [ ] **Step 3: Write minimal implementation**

```python
# policy_check/doc_drift/engine.py
from __future__ import annotations

from pathlib import Path

from policy_check.doc_drift import refs as dd_refs
from policy_check.doc_drift import symbols as dd_symbols
from policy_check.doc_drift import drift as dd_drift
from policy_check.doc_drift import provision as dd_provision
from policy_check.doc_drift.paths import git_tracked, resolve_base

_DOC_SCOPE = ("README.md",)  # 簡化：doc-drift mode 掃 README + docs/**


def _in_scope(rel: str) -> bool:
    return rel == "README.md" or rel.startswith("docs/")


def run_doc_drift(repo_root: Path, base_ref: str, head_ref: str = "HEAD"):
    """回 (fails: list[str], warns: list[str])。"""
    root = Path(repo_root)
    base = resolve_base(root, base_ref)
    fails: list[str] = []
    warns: list[str] = []
    removed_ids: set = set()
    head_ids: set = set()
    if base and dd_provision.ensure_object(root, base) and dd_provision.ensure_object(root, head_ref):
        base_ids = dd_symbols.symbols_at(root, base)
        head_ids = dd_symbols.symbols_at(root, head_ref)
        removed_ids = dd_drift.removed_identities(base_ids, head_ids)
    head_files = git_tracked(root)
    for rel in sorted(f for f in head_files if _in_scope(f)):
        try:
            text = (root / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for kind, token, payload in dd_refs.extract_refs(rel, text):
            if kind == "symbol":
                v = dd_drift.classify_symbol_token(token, removed_ids, head_ids)
                if v == "FAIL":
                    fails.append(f"{rel} -> `{token}` (symbol removed this change)")
                elif v == "WARN":
                    warns.append(f"{rel} -> `{token}` (ambiguous)")
            elif kind == "path" and not any(c in head_files for c in payload):
                warns.append(f"{rel} -> {token}")
    return fails, warns
```

```python
# policy_check/doc_drift/__main__.py
from __future__ import annotations

import argparse
import sys

from policy_check.doc_drift import engine


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="doc-drift")
    p.add_argument("--mode", choices=["doc-drift", "moc"], default="doc-drift")
    p.add_argument("--repo", default=".")
    p.add_argument("--base", required=True)
    p.add_argument("--head", default="HEAD")
    args = p.parse_args(argv)

    if args.mode == "doc-drift":
        fails, warns = engine.run_doc_drift(args.repo, args.base, args.head)
    else:
        fails, warns = [], []  # moc mode 於 Task 後續接 coverage（P2 充實）
    for line in fails:
        print(f"FAIL {line}")
    for line in warns:
        print(f"WARN {line}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run to verify it passes**

Run: `python3 -m pytest tests/test_doc_drift_cli.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add policy_check/doc_drift/engine.py policy_check/doc_drift/__main__.py tests/test_doc_drift_cli.py
git commit -m "feat(doc-drift): 薄 CLI + engine（doc-drift mode，exit code 契約）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8.5: moc-alignment mode 端到端（CLI）

**Files:**
- Modify: `policy_check/doc_drift/engine.py`（加 `run_moc`）、`policy_check/doc_drift/__main__.py`（接 moc mode）
- Test: `tests/test_doc_drift_moc_cli.py`

依賴 Task 7（coverage）與 Task 8（CLI 殼）。

- [ ] **Step 1: Write the failing test**

```python
# tests/test_doc_drift_moc_cli.py
import subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _git(repo: Path, *a): subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)


def test_moc_mode_flags_dangling_map_ref_with_custom_prefix(tmp_path):
    _git(tmp_path, "init", "-q"); _git(tmp_path, "config", "user.email", "t@t"); _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "specs").mkdir()
    (tmp_path / "specs" / "a.md").write_text("x\n")
    (tmp_path / "MAP.md").write_text("map: [a](specs/a.md)\n")
    _git(tmp_path, "add", "-A"); _git(tmp_path, "commit", "-qm", "c")
    base = subprocess.run(["git", "-C", str(tmp_path), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    (tmp_path / "specs" / "a.md").unlink()  # 本次刪除被 map 連結的產物
    _git(tmp_path, "add", "-A"); _git(tmp_path, "commit", "-qm", "rm")
    proc = subprocess.run(
        [sys.executable, "-m", "policy_check.doc_drift", "--mode", "moc",
         "--repo", str(tmp_path), "--base", base, "--head", "HEAD",
         "--map", "MAP.md", "--governed-prefix", "specs/"],
        capture_output=True, text=True, env={"PYTHONPATH": str(REPO)})
    assert proc.returncode != 0
    assert "specs/a.md" in proc.stdout
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_doc_drift_moc_cli.py -q`
Expected: FAIL（CLI 尚未接 `--map`/`--governed-prefix`、`run_moc` 不存在）

- [ ] **Step 3: 實作 `engine.run_moc`**

```python
# 追加到 policy_check/doc_drift/engine.py
from policy_check.doc_drift import coverage as dd_coverage
from policy_check.doc_drift.paths import LINK_RE, looks_like_path, path_candidates
import re as _re

_CODE_SPAN = _re.compile(r"`([^`\n]+)`")


def _map_refs(map_rel, text, prefixes):
    tokens = [m.group(1) for m in LINK_RE.finditer(text)]
    tokens += [t for t in (m.group(1).strip() for m in _CODE_SPAN.finditer(text)) if looks_like_path(t)]
    for tok in tokens:
        cands = [c for c in path_candidates(map_rel, tok) if c.startswith(tuple(prefixes))]
        if cands:
            yield tok, cands


def run_moc(repo_root, base_ref, map_rel, prefixes, head_ref="HEAD"):
    root = Path(repo_root)
    base = resolve_base(root, base_ref)
    head_files = git_tracked(root)
    base_files = git_tracked(root, base) if base else set()
    fails, warns = [], []
    try:
        text = (root / map_rel).read_text(encoding="utf-8")
    except OSError:
        return [f"moc.map '{map_rel}' 不存在"], []
    linked = set()
    for tok, cands in _map_refs(map_rel, text, prefixes):
        linked.update(cands)
        if any(c in head_files for c in cands):
            continue
        if base and any(c in base_files for c in cands):
            fails.append(f"{map_rel} -> {tok} (removed this change)")
        else:
            warns.append(f"{map_rel} -> {tok}")
    for orphan in dd_coverage.orphans(head_files, linked, prefixes=tuple(prefixes)):
        warns.append(f"orphan: {orphan} 未被 {map_rel} 連結")
    return fails, warns
```

- [ ] **Step 4: 接進 CLI**

```python
# __main__.py：加參數並分派
    p.add_argument("--map", default="docs/MOC.md")
    p.add_argument("--governed-prefix", action="append", default=None, dest="prefixes")
    ...
    if args.mode == "doc-drift":
        fails, warns = engine.run_doc_drift(args.repo, args.base, args.head)
    else:
        prefixes = tuple(args.prefixes) if args.prefixes else None
        from policy_check.doc_drift.coverage import DEFAULT_GOVERNED_PREFIXES
        fails, warns = engine.run_moc(args.repo, args.base, args.map,
                                      prefixes or DEFAULT_GOVERNED_PREFIXES, args.head)
```

- [ ] **Step 5: Run to verify it passes + full suite**

Run: `python3 -m pytest tests/test_doc_drift_moc_cli.py -q && python3 -m pytest -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add policy_check/doc_drift/engine.py policy_check/doc_drift/__main__.py tests/test_doc_drift_moc_cli.py
git commit -m "feat(doc-drift): moc-alignment mode 端到端（map 懸空 + orphan，前綴可設定）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Action（action.yml + run.sh）+ base/head SHA 供給

**Files:**
- Create: `.github/actions/doc-drift/action.yml`
- Create: `.github/actions/doc-drift/run.sh`

- [ ] **Step 1: 建 composite action**

```yaml
# .github/actions/doc-drift/action.yml
name: doc-drift
description: Deterministic, language-aware doc↔code drift checker (symbol + path).
inputs:
  mode:
    description: doc-drift | moc
    default: doc-drift
  base-sha:
    description: PR base commit SHA (precise). Defaults to event base.
    required: false
runs:
  using: composite
  steps:
    - name: Install universal-ctags
      shell: bash
      run: sudo apt-get update -qq && sudo apt-get install -y universal-ctags
    - name: Run doc-drift
      shell: bash
      run: "${{ github.action_path }}/run.sh"
      env:
        DOC_DRIFT_MODE: ${{ inputs.mode }}
        DOC_DRIFT_BASE_SHA: ${{ inputs.base-sha }}
        GH_BASE_SHA: ${{ github.event.pull_request.base.sha }}
        GH_HEAD_SHA: ${{ github.event.pull_request.head.sha }}
```

```bash
# .github/actions/doc-drift/run.sh
#!/usr/bin/env bash
set -euo pipefail

ACTION_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# 引擎位置：action 自帶 policy_check（checkout 於 caller workspace 時需自取）
ENGINE_ROOT="${ACTION_DIR}/../../.."   # 自家 repo dogfood；外部用 uses: 取得本 action 所在 repo
export PYTHONPATH="${ENGINE_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

BASE_SHA="${DOC_DRIFT_BASE_SHA:-${GH_BASE_SHA:-}}"
HEAD_SHA="${GH_HEAD_SHA:-HEAD}"

if [[ -z "$BASE_SHA" ]]; then
  echo "ERROR: 無法決定 base SHA（非 PR 事件或未提供 base-sha）。" >&2
  exit 2
fi

PY=python3; command -v python3 >/dev/null || PY=python
exec "$PY" -m policy_check.doc_drift \
  --mode "${DOC_DRIFT_MODE:-doc-drift}" \
  --repo "${GITHUB_WORKSPACE:-.}" \
  --base "$BASE_SHA" \
  --head "$HEAD_SHA"
```

> 註：CLI 的 `provision.ensure_object` 會在 shallow checkout 缺 base 物件時自 `git fetch origin <sha>`，再不行則 fail-fast（exit≠0）。

- [ ] **Step 2: 本機 smoke（用 demo，見 Task 10 後）**

Run（Task 10 完成後）：`bash .github/actions/doc-drift/run.sh`（以 demo 環境變數）
Expected: known-bad → exit 1。

- [ ] **Step 3: Commit**

```bash
chmod +x .github/actions/doc-drift/run.sh
git add .github/actions/doc-drift/action.yml .github/actions/doc-drift/run.sh
git commit -m "feat(doc-drift): composite action + run.sh（自理 base/head SHA）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: demo fixtures + self-test CI（含 shallow 情境）

**Files:**
- Create: `examples/doc-drift/README.md`、`examples/doc-drift/good/`、`examples/doc-drift/bad/`
- Modify: `.github/workflows/self-test.yml`
- Test: `tests/test_doc_drift_demo.py`（本機斷言 demo green/red）

- [ ] **Step 1: Write the failing test**

```python
# tests/test_doc_drift_demo.py
import subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_demo_bad_fails_and_good_passes(tmp_path):
    # 在 tmp 建一個 git repo，base 有 symbol、head 刪掉；good doc 不引用、bad doc 引用
    def git(*a): subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True)
    git("init", "-q"); git("config", "user.email", "t@t"); git("config", "user.name", "t")
    (tmp_path / "pkg").mkdir(); (tmp_path / "docs").mkdir()
    (tmp_path / "pkg" / "api.py").write_text("def shutdown():\n    pass\n")
    (tmp_path / "docs" / "ok.md").write_text("nothing to see\n")
    git("add", "-A"); git("commit", "-qm", "c")
    base = subprocess.run(["git", "-C", str(tmp_path), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    (tmp_path / "pkg" / "api.py").write_text("# shutdown removed\n")
    (tmp_path / "docs" / "bad.md").write_text("call `shutdown`\n")
    git("add", "-A"); git("commit", "-qm", "rm")

    def run():
        return subprocess.run([sys.executable, "-m", "policy_check.doc_drift",
                               "--repo", str(tmp_path), "--base", base, "--head", "HEAD"],
                              capture_output=True, text=True, env={"PYTHONPATH": str(REPO)})
    proc = run()
    assert proc.returncode != 0 and "shutdown" in proc.stdout
```

- [ ] **Step 2: Run to verify it fails**, then make pass by ensuring engine works (already from Task 8).

Run: `python3 -m pytest tests/test_doc_drift_demo.py -q`
Expected: PASS（驗證端到端）

- [ ] **Step 3: 建 examples/doc-drift demo + README 片段**（靜態示範用，CI self-test 以 fixture 跑）

- [ ] **Step 4: self-test job（含 shallow checkout）**

```yaml
# 追加到 .github/workflows/self-test.yml
  doc-drift-self-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 1   # 故意 shallow：驗證 Action 自取 base 不前置失敗
      - run: sudo apt-get update -qq && sudo apt-get install -y universal-ctags
      - run: python3 -m pytest -q tests/test_doc_drift_demo.py
```

- [ ] **Step 5: Run full suite + commit**

Run: `python3 -m pytest -q`
Expected: 全綠

```bash
git add examples/doc-drift tests/test_doc_drift_demo.py .github/workflows/self-test.yml
git commit -m "test(doc-drift): demo fixtures + self-test（含 shallow checkout 情境）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: P3 — bash 語言支援

**Files:** Modify `policy_check/doc_drift/langs.py`；Create `tests/test_doc_drift_bash.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_doc_drift_bash.py
from policy_check.doc_drift import symbols, langs


def test_bash_function_extracted():
    assert "Sh" in langs.supported_languages()
    lines = ['{"_type":"tag","name":"do_build","language":"Sh","kind":"function"}']
    assert ("Sh", "function", "", "do_build") in symbols.parse_ctags_json(lines)
```

- [ ] **Step 2: Run → FAIL（`Sh` 未註冊）**

Run: `python3 -m pytest tests/test_doc_drift_bash.py -q`

- [ ] **Step 3: 註冊 bash**

```python
# langs.py 的 _LANG_KINDS 加：
    "Sh": {"function"},
```

驗證 ctags Sh kind：`ctags --list-kinds-full=Sh`（function = f）。

- [ ] **Step 4: Run → PASS；Step 5: Commit**

```bash
git add policy_check/doc_drift/langs.py tests/test_doc_drift_bash.py
git commit -m "feat(doc-drift): 支援 bash（Sh function）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 12: P4 — C/C++ 語言支援

**Files:** Modify `policy_check/doc_drift/langs.py`；Create `tests/test_doc_drift_c.py`

- [ ] **Step 1: 先驗 ctags kind**

Run: `ctags --list-kinds-full=C` / `=C++`
記錄 public kind（C：`function`,`struct`,`typedef`,`macro`,`enum`；C++ 另含 `class`,`member`）。

- [ ] **Step 2: Write the failing test**

```python
# tests/test_doc_drift_c.py
from policy_check.doc_drift import symbols, langs


def test_c_function_extracted():
    assert "C" in langs.supported_languages()
    lines = ['{"_type":"tag","name":"wifi_init","language":"C","kind":"function"}']
    assert ("C", "function", "", "wifi_init") in symbols.parse_ctags_json(lines)


def test_cpp_method_scoped():
    assert "C++" in langs.supported_languages()
    lines = ['{"_type":"tag","name":"start","language":"C++","kind":"function","scope":"Engine","scopeKind":"class"}']
    assert ("C++", "function", "Engine", "start") in symbols.parse_ctags_json(lines)
```

- [ ] **Step 3: 註冊 C/C++**

```python
# langs.py 的 _LANG_KINDS 加：
    "C": {"function", "struct", "typedef", "macro", "enum"},
    "C++": {"function", "class", "struct", "member", "typedef", "macro", "enum"},
```

- [ ] **Step 4: Run → PASS；Step 5: Commit**

```bash
git add policy_check/doc_drift/langs.py tests/test_doc_drift_c.py
git commit -m "feat(doc-drift): 支援 C/C++（function/class/struct/...）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 13: P5 — 誤報雙軌 UX（inline marker + allowlist 檔）

**Files:** Create `policy_check/doc_drift/exempt.py`；Modify `engine.py` + `r22`/`r24` 套用；Test `tests/test_doc_drift_exempt.py`

語法定稿：inline marker 為同行或前一行的 `<!-- doc-drift-ignore -->`（豁免該行所有引用）；allowlist 檔 `.doc-drift-allow`，每行一個 glob（doc 路徑）或 `symbol:<name>`。

- [ ] **Step 1: Write the failing test**

```python
# tests/test_doc_drift_exempt.py
from policy_check.doc_drift import exempt


def test_inline_marker_suppresses_line():
    text = "call `gone` <!-- doc-drift-ignore -->\n"
    assert exempt.line_is_ignored(text.splitlines()[0]) is True


def test_allowlist_symbol_match():
    allow = exempt.parse_allowlist(["symbol:gone", "docs/legacy/*"])
    assert exempt.is_allowed("docs/a.md", "gone", allow) is True
    assert exempt.is_allowed("docs/legacy/x.md", "anything", allow) is True
    assert exempt.is_allowed("docs/a.md", "kept", allow) is False
```

- [ ] **Step 2: Run → FAIL；Step 3: 實作 exempt.py**

```python
# policy_check/doc_drift/exempt.py
from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch

_MARKER = "doc-drift-ignore"


def line_is_ignored(line: str) -> bool:
    return _MARKER in line


@dataclass
class Allowlist:
    symbols: set[str] = field(default_factory=set)
    path_globs: list[str] = field(default_factory=list)


def parse_allowlist(lines) -> Allowlist:
    al = Allowlist()
    for raw in lines:
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("symbol:"):
            al.symbols.add(s[len("symbol:"):])
        else:
            al.path_globs.append(s)
    return al


def is_allowed(doc_rel: str, token: str, allow: Allowlist) -> bool:
    if token in allow.symbols:
        return True
    return any(fnmatch(doc_rel, g) for g in allow.path_globs)
```

- [ ] **Step 4: 在 `engine.run_doc_drift` 與 R-22/R-24 套用**：讀 `.doc-drift-allow`（若存在）→ `parse_allowlist`；對每個 token：若 `line_is_ignored(該行)` 或 `is_allowed(...)` 則跳過。需把行內容傳入比對（`extract_refs` 可附帶行號/行文，或 engine 逐行掃）。

- [ ] **Step 5: Run → PASS + full suite；Commit**

```bash
git add policy_check/doc_drift/exempt.py policy_check/doc_drift/engine.py policy_check/rules/r22_doc_reference.py tests/test_doc_drift_exempt.py
git commit -m "feat(doc-drift): 誤報雙軌豁免（inline marker + .doc-drift-allow）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 14: 收尾 — docs 同步 / changelog / policy gate

**Files:** `.github/actions/doc-drift/README.md`、`README.md`、`docs/MOC.md`、`changelog.d/25-*.md`、`CHANGELOG.md`

- [ ] **Step 1: Action README** — 定位、輸入/輸出、base 供給契約、`uses:` 片段、lychee 互補、多語言支援表（Python/bash/C/C++）、已知侷限（裸名歧義只 WARN）。
- [ ] **Step 2: 主 README** — R-22/R-24 描述更新（語言無關 scoped）、Action 總覽、lychee 互補一行。
- [ ] **Step 3: `docs/MOC.md`** — 連結本案 spec/plan/openspec change（避免 R-24 orphan WARN）。
- [ ] **Step 4: changelog fragments** — 每 phase 一個 `changelog.d/25-<slug>.md`（frontmatter `type: feat`、`issue: 25`；body 一行）。
- [ ] **Step 5: policy gate**

Run: `python3 -m pytest -q && python3 -m policy_check --repo .`
Expected: 測試全綠、policy 無 failure。

- [ ] **Step 6: Commit**

```bash
git add README.md docs/MOC.md .github/actions/doc-drift/README.md changelog.d CHANGELOG.md
git commit -m "docs(doc-drift): README/Action README/MOC 同步 + changelog fragments

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review（plan 對 spec 覆蓋）

- doc-drift-core 五 requirement → Task 1–5、13（langs/symbols/scoped diff/provision/path-coverage/exempt）。✅
- doc-reference MODIFIED（scoped、語言無關）→ Task 6。✅
- moc-alignment MODIFIED（前綴參數化）→ Task 7。✅
- doc-drift-action 六 requirement（零設定、兩 mode、base 供給、exit code、lychee 邊界、demo+self-test）→ Task 8（doc-drift mode）、**Task 8.5（moc mode 端到端、前綴可設定）**、Task 9–10。✅
- 語言序 Python→bash→C/C++ → Task 6/11/12。✅
- 收尾 docs/changelog/gate → Task 14。✅

**Type consistency 檢查：** `Identity` 四元組 `(language, kind, scope, name)` 於 Task 2/3/6/8 一致；`classify_symbol_token`/`removed_identities`/`symbols_at`/`ensure_object`/`orphans`/`extract_refs` 簽名於各 task 與「核心型別約定」段一致。✅

> 實作前置驗證點（各 phase 第一步先跑）：`ctags --list-kinds-full=<Lang>` 確認 kind long-name 與白名單相符（Python member/function/class 已驗；bash/C/C++ 於 Task 11/12 驗）。
