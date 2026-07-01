# Rule Families + README 版號 generated-fact 自我強制 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓 `policy_check` 報告依規則 family 分組（呈現層，零 `rule_id` 變動），並把 README 手抄版號改由既有 R-26 `generated_facts` 每個 PR 強制同步。

**Architecture:** 新增中央有序分類 `policy_check/rules/families.py`；`report.emit` 依 family 分組並以尾端 `OTHER` catch-all 保證「body 逐條區塊數 == summary 計數」；`cli.py` 傳入 `rule_id→family` 映射。README 版號改為 `repo-version` generated-fact marker、去除 L21/L269 手抄字面；`.paul-project.yml` 宣告一個 `generated_facts` entry。不動任何 `rule_id`／exemption label／R-26 規則本體。

**Tech Stack:** Python 3.11+、pytest、既有 `policy_check` 引擎（`_marker_sync`、registry、report）。

**對應 spec：** `docs/superpowers/specs/2026-07-01-rule-families-and-version-fact-design.md`、`openspec/changes/rule-families-version-fact/`。

**全程慣例：** 在 worktree（分支 `feature/rule-families-version-fact`）；每 code task TDD-first（先紅）；commit 訊息 zh-tw + `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`；測試 `python3 -m pytest -q`。

---

## File Structure

- Create `policy_check/rules/families.py` — 中央有序 rule→family 分類 + 查詢函式。
- Modify `policy_check/report.py` — `emit(results, families=None)` 分組 + OTHER catch-all。
- Modify `policy_check/cli.py` — 組 family map 並傳給 `emit`。
- Create `tests/test_families.py`、`tests/test_report_grouping.py`、`tests/test_r26_dogfood.py`。
- Modify `README.md` — L271 版號 marker、L269 去規則數、L21 去 policy_version 字面。
- Modify `.paul-project.yml` — 新增 `generated_facts`。
- Modify `docs/MOC.md`、`RELEASES.md`。
- Create `changelog.d/rule-families-version-fact.md`。

---

## Task 1: families.py 中央分類 + 完整性測試

**Files:**
- Create: `policy_check/rules/families.py`
- Test: `tests/test_families.py`

- [ ] **Step 1: 先寫失敗測試**

```python
# tests/test_families.py
from policy_check.rules import families, registry


def test_family_of_known():
    assert families.family_of("R-05") == "VERSION"
    assert families.family_of("R-01") == "README"
    assert families.family_of("R-26") == "MARKER-SYNC"


def test_family_of_unknown_is_other():
    assert families.family_of("R-99") == "OTHER"


def test_ordered_families_excludes_other_and_matches_source():
    of = families.ordered_families()
    assert of == [fam for fam, _ in families.FAMILIES]
    assert "OTHER" not in of
    assert of[0] == "README"


def test_every_registered_rule_classified_exactly_once():
    reg_ids = sorted(r.rule_id for r in registry.load_all())
    classified = [rid for _fam, rids in families.FAMILIES for rid in rids]
    assert len(classified) == len(set(classified)), "FAMILIES 有重複 rule_id"
    classified_set = set(classified)
    missing = [rid for rid in reg_ids if rid not in classified_set]
    assert not missing, f"未分類規則：{missing}"
    unknown = [rid for rid in classified_set if rid not in set(reg_ids)]
    assert not unknown, f"FAMILIES 含未知 rule_id：{unknown}"
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python3 -m pytest tests/test_families.py -q`
Expected: FAIL — `ModuleNotFoundError: policy_check.rules.families`

- [ ] **Step 3: 實作 families.py**

```python
# policy_check/rules/families.py
"""規則 → family 的中央有序分類（純呈現層）。

不觸及 rule_id / exempt_label / 規則行為。新增規則須在此登記其 id；
tests/test_families.py 的完整性測試保證每個註冊規則恰好被分類一次。
"""
from __future__ import annotations

# 順序即報告輸出順序。每個 rule_id 恰好屬一個 family。
FAMILIES: list[tuple[str, tuple[str, ...]]] = [
    ("README", ("R-01", "R-02")),
    ("CHANGELOG", ("R-03", "R-04", "R-09")),
    ("VERSION", ("R-05", "R-06", "R-07")),
    ("CONFIG", ("R-08",)),
    ("PR", ("R-10", "R-11", "R-12", "R-17")),
    ("AGENT", ("R-13", "R-14")),
    ("WORKFLOW", ("R-15", "R-20", "R-23")),
    ("MARKER-SYNC", ("R-16", "R-26")),
    ("CI", ("R-19",)),
    ("SECRET", ("R-21",)),
    ("DOC-ALIGN", ("R-18", "R-22", "R-24", "R-25")),
]

OTHER = "OTHER"

_RULE_TO_FAMILY = {rid: fam for fam, rids in FAMILIES for rid in rids}


def family_of(rule_id: str) -> str:
    """回 rule_id 所屬 family；未分類回 OTHER。"""
    return _RULE_TO_FAMILY.get(rule_id, OTHER)


def ordered_families() -> list[str]:
    """family 名的輸出順序（不含 OTHER；OTHER 由 report 尾端 catch-all 處理）。"""
    return [fam for fam, _ in FAMILIES]
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python3 -m pytest tests/test_families.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add policy_check/rules/families.py tests/test_families.py
git commit -m "feat(report): 中央 rule→family 分類 families.py（含完整性測試）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: report.emit 分組 + OTHER catch-all

**Files:**
- Modify: `policy_check/report.py`
- Test: `tests/test_report_grouping.py`

- [ ] **Step 1: 先寫失敗測試**

```python
# tests/test_report_grouping.py
import io
import re
import contextlib

from policy_check.report import emit
from policy_check.rules.base import RuleResult, Status


def _cap(results, families=None, monkeypatch=None):
    if monkeypatch is not None:
        monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = emit(results, families)
    return buf.getvalue(), rc


def _mk(rid, status=Status.PASS):
    return RuleResult(rid, status, f"msg {rid}")


def _rule_block_count(out):
    # 逐條規則區塊標題形如 "## :icon: R-NN — status"；family 標題為 "### FAM"
    return len(re.findall(r"^## :", out, re.M))


def test_grouped_output_has_family_headers_in_order(monkeypatch):
    results = [_mk("R-05"), _mk("R-01"), _mk("R-06")]
    fam = {"R-05": "VERSION", "R-01": "README", "R-06": "VERSION"}
    out, rc = _cap(results, fam, monkeypatch)
    assert "### README" in out and "### VERSION" in out
    assert out.index("### README") < out.index("### VERSION")
    assert out.index("R-05") < out.index("R-06")  # family 內按 rule_id
    assert rc == 0


def test_families_none_is_flat_backward_compat(monkeypatch):
    results = [_mk("R-05"), _mk("R-01")]
    out, rc = _cap(results, None, monkeypatch)
    assert "###" not in out
    assert out.index("R-01") < out.index("R-05")
    assert rc == 0


def test_unclassified_rule_goes_to_other_and_count_matches(monkeypatch):
    results = [_mk("R-01"), _mk("R-99")]      # R-99 不在 map
    fam = {"R-01": "README"}
    out, rc = _cap(results, fam, monkeypatch)
    assert "### OTHER" in out
    assert "R-99" in out
    assert _rule_block_count(out) == 2        # body 區塊數 == summary 總數


def test_exit_code_1_on_fail_regardless_of_grouping(monkeypatch):
    _, rc = _cap([_mk("R-01", Status.FAIL)], {"R-01": "README"}, monkeypatch)
    assert rc == 1
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python3 -m pytest tests/test_report_grouping.py -q`
Expected: FAIL — `emit()` 不接受第二個參數 / 無 family 標題

- [ ] **Step 3: 改寫 report.py 的 emit**

把 `policy_check/report.py` 全檔換成：

```python
# policy_check/report.py
import os
from typing import Iterable

from policy_check.rules.base import RuleResult, Status
from policy_check.rules.families import ordered_families, OTHER

_ICON = {
    "pass": ":white_check_mark:",
    "fail": ":x:",
    "skip": ":warning:",
    "warn": ":warning:",
}


def _render_rule(r: RuleResult) -> list[str]:
    block = [f"## {_ICON[r.status.value]} {r.rule_id} — {r.status.value}", r.message]
    if r.exempt_label:
        block.append(f"exempt via: `{r.exempt_label}`")
    if r.detail:
        block.append(f"\n<details><summary>detail</summary>\n\n```\n{r.detail}\n```\n\n</details>")
    block.append("")
    return block


def emit(results: Iterable[RuleResult], families: dict | None = None) -> int:
    results = list(results)
    lines = ["# Policy Check Report\n"]
    fails = [r for r in results if r.status == Status.FAIL]
    skips = [r for r in results if r.status == Status.SKIP]
    passes = [r for r in results if r.status == Status.PASS]
    warns = [r for r in results if r.status == Status.WARN]

    lines.append(f"- pass: {len(passes)}")
    lines.append(f"- fail: {len(fails)}")
    lines.append(f"- warn: {len(warns)}")
    lines.append(f"- skip (exempt): {len(skips)}\n")

    if families is None:
        # 向後相容：無 family map 時依 rule_id 平鋪
        for r in sorted(results, key=lambda x: x.rule_id):
            lines += _render_rule(r)
    else:
        by_family: dict[str, list[RuleResult]] = {}
        for r in results:
            by_family.setdefault(families.get(r.rule_id, OTHER), []).append(r)
        emitted: set[int] = set()
        for fam in ordered_families():
            group = by_family.get(fam)
            if not group:
                continue
            lines.append(f"### {fam}")
            lines.append("")
            for r in sorted(group, key=lambda x: x.rule_id):
                lines += _render_rule(r)
                emitted.add(id(r))
        # OTHER catch-all：family 不在 ordered_families()（含未分類）者，確保不被漏印
        leftovers = [r for r in results if id(r) not in emitted]
        if leftovers:
            lines.append(f"### {OTHER}")
            lines.append("")
            for r in sorted(leftovers, key=lambda x: x.rule_id):
                lines += _render_rule(r)

    report = "\n".join(lines)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a") as f:
            f.write(report)
    else:
        print(report)

    return 1 if fails else 0
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python3 -m pytest tests/test_report_grouping.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: 跑全 suite 確認無迴歸**

Run: `python3 -m pytest -q`
Expected: 全綠（既有 report/integration 測試只查 `# Policy Check Report` 子字串，格式改動不破壞）

- [ ] **Step 6: Commit**

```bash
git add policy_check/report.py tests/test_report_grouping.py
git commit -m "feat(report): emit 依 family 分組 + OTHER catch-all（body==summary 不變量）

- emit(results, families=None)：families 為 None 時回舊平鋪（向後相容）
- 分組走訪 ordered_families() + 尾端 OTHER 收納未分類/未知，保證無結果被漏印
- per-rule 區塊格式、summary、exit code 契約不變

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: cli.py 傳入 family map

**Files:**
- Modify: `policy_check/cli.py`

- [ ] **Step 1: 加 import**

在 `policy_check/cli.py` 的 import 區（第 9 行 `from policy_check.rules import registry` 之後）加：

```python
from policy_check.rules import families
```

- [ ] **Step 2: 改 emit 呼叫**

把 `main()` 內（原第 57–58 行）：

```python
    results = [r.check(ctx) for r in rules]
    return emit(results)
```

換成：

```python
    results = [r.check(ctx) for r in rules]
    family_map = {r.rule_id: families.family_of(r.rule_id) for r in rules}
    return emit(results, family_map)
```

- [ ] **Step 3: 手動驗證**

Run: `python3 -m policy_check --repo .`
Expected: 報告出現 `### VERSION`、`### DOC-ALIGN` 等 family 標題；頂部 summary 計數與退出碼與改前一致。

Run: `python3 -m policy_check --repo . --only R-05,R-06`
Expected: 只印 `### VERSION`（其餘空 family 不印）。

- [ ] **Step 4: 全 suite**

Run: `python3 -m pytest -q`
Expected: 全綠

- [ ] **Step 5: Commit**

```bash
git add policy_check/cli.py
git commit -m "feat(cli): 傳 rule→family 映射給 report.emit（啟用分組輸出）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: README 訂正（版號 marker + 去手抄字面）

**Files:**
- Modify: `README.md`

- [ ] **Step 1: L271 版號 → repo-version generated-fact marker**

把 README.md 中這行（約 L271）：

```
當前版本：見 `VERSION`（現為 `1.0.7`）。
```

換成（marker 區塊只放版號一行，值 = 動工當下的 `VERSION`，現為 `1.0.10`；**勿**填 header 目標 1.0.11）：

```
當前版本（權威值見 `VERSION`）：

<!-- BEGIN: generated-fact marker="repo-version" -->
1.0.10
<!-- END: generated-fact marker="repo-version" -->
```

- [ ] **Step 2: L269 去規則數字面**

把（約 L269）：

```
- **PATCH**: 累積已完成的 feature batch 計數（本 repo 為 R-01~R-23 完整實作）
```

換成：

```
- **PATCH**: 累積已完成的 feature batch 計數（完整規則清單見 `RELEASES.md` / `CHANGELOG.md`）
```

- [ ] **Step 3: L21 去 policy_version 字面**

把（約 L21）：

```
本 repo 自身亦 **dog-food** 本套 policy（`profile: flat`, `policy_version: 1.0.10`）。
```

換成：

```
本 repo 自身亦 **dog-food** 本套 policy（`profile: flat`；`policy_version` 見 `.paul-project.yml` / `VERSION`）。
```

- [ ] **Step 4: 確認 README 內無第二個 repo-version marker**

Run: `grep -c 'marker="repo-version"' README.md`
Expected: `2`（僅一組 BEGIN/END）。若 >2，表示散文中有重複字面 pair，須改用佔位名。

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs(readme): 版號改 repo-version generated-fact marker + 去 L21/L269 手抄字面

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: dogfood R-26（.paul-project.yml）+ green/red 測試

**Files:**
- Modify: `.paul-project.yml`
- Test: `tests/test_r26_dogfood.py`

- [ ] **Step 1: 先寫失敗測試（用 CLI 子行程，穩健）**

```python
# tests/test_r26_dogfood.py
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

_CFG = """policy_profile: flat
policy_version: 1.0.10
generated_facts:
  - command: "cat VERSION"
    reflected_in: "README.md"
    marker: "repo-version"
"""
_MARK = (
    '<!-- BEGIN: generated-fact marker="repo-version" -->\n'
    "{v}\n"
    '<!-- END: generated-fact marker="repo-version" -->\n'
)


def _setup(root: Path, marker_version: str, file_version: str) -> None:
    (root / ".paul-project.yml").write_text(_CFG)
    (root / "VERSION").write_text(file_version + "\n")
    (root / "README.md").write_text("# demo\n\n" + _MARK.format(v=marker_version))


def _run_r26(root: Path):
    return subprocess.run(
        [sys.executable, "-m", "policy_check", "--repo", str(root), "--only", "R-26"],
        capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(REPO)},
    )


def test_r26_dogfood_green_when_marker_matches_version(tmp_path):
    _setup(tmp_path, marker_version="1.0.10", file_version="1.0.10")
    proc = _run_r26(tmp_path)
    assert proc.returncode == 0, proc.stdout


def test_r26_dogfood_red_when_marker_drifts_from_version(tmp_path):
    # VERSION bump 到 1.0.11 但 README marker 仍 1.0.10 → 應被擋
    _setup(tmp_path, marker_version="1.0.10", file_version="1.0.11")
    proc = _run_r26(tmp_path)
    assert proc.returncode == 1
    assert "R-26" in proc.stdout
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python3 -m pytest tests/test_r26_dogfood.py -q`
Expected: 兩案皆能跑；紅案應如預期。此步主要驗測試本身可跑（R-26 行為既有）。

- [ ] **Step 3: 在 .paul-project.yml 宣告 generated_facts**

在 `.paul-project.yml` 末端（`moc:` 區塊之後）追加：

```yaml
generated_facts:
  - command: "cat VERSION"
    reflected_in: "README.md"
    marker: "repo-version"
```

- [ ] **Step 4: 驗本 repo R-26 由 NA 轉 PASS**

Run: `python3 -m policy_check --repo . --only R-26`
Expected: R-26 PASS（README `repo-version` marker == `cat VERSION` == `1.0.10`）。若 FAIL，檢查 Task 4 marker 內容是否恰為 `1.0.10` 一行。

- [ ] **Step 5: 全 suite + 全 gate**

Run: `python3 -m pytest -q`
Expected: 全綠

Run: `python3 -m policy_check --repo .`
Expected: 無 fail（R-08 接受新 `generated_facts`；R-26 PASS）。

- [ ] **Step 6: Commit**

```bash
git add .paul-project.yml tests/test_r26_dogfood.py
git commit -m "feat(dogfood): 啟用 R-26 generated_facts 守 README 版號（cat VERSION↔repo-version marker）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: docs/MOC.md 連結 + RELEASES.md SOP

**Files:**
- Modify: `docs/MOC.md`、`RELEASES.md`

- [ ] **Step 1: docs/MOC.md 連結本 spec/plan**

在 `docs/MOC.md` 的 Plans 段加一行：

```
- [rule families + 版號 generated-fact（無 issue）](superpowers/plans/2026-07-01-rule-families-and-version-fact.md) — 進行中
```

在 Specs 段加一行：

```
- [rule families + 版號 generated-fact design（無 issue）](superpowers/specs/2026-07-01-rule-families-and-version-fact-design.md) — 進行中
```

- [ ] **Step 2: RELEASES.md 升版 SOP 補一條**

在 `RELEASES.md` 的升版 SOP 步驟清單中，於「bump 版號檔」相關步驟旁補一條：

```
- 更新 README 的 `repo-version` generated-fact marker 為新 `VERSION`（R-26 為安全網，漏改則 release PR CI 會擋）。
```

- [ ] **Step 3: 驗 R-24 orphan WARN 已消**

Run: `python3 -m policy_check --repo . --only R-24`
Expected: R-24 PASS 或不再列出本 spec/plan 為 orphan。

- [ ] **Step 4: Commit**

```bash
git add docs/MOC.md RELEASES.md
git commit -m "docs: MOC 連結本 spec/plan + RELEASES SOP 補 repo-version marker 更新

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: changelog fragment + 收尾驗收

**Files:**
- Create: `changelog.d/rule-families-version-fact.md`

- [ ] **Step 1: 新增 changelog fragment**

```markdown
---
type: feat
scope: report
---
policy_check 報告改依規則 family 分組呈現（中央有序分類 + OTHER catch-all，零 rule_id/label 變動）；README 版號改由 R-26 generated-fact marker 每 PR 強制同步、去除 L21/L269 手抄版號字面。
```

- [ ] **Step 2: openspec validate**

Run: `openspec validate rule-families-version-fact --strict`
Expected: `Change 'rule-families-version-fact' is valid`

- [ ] **Step 3: 全 suite**

Run: `python3 -m pytest -q`
Expected: 全綠

- [ ] **Step 4: 全 policy gate**

Run: `python3 -m policy_check --repo .`
Expected: 無 fail。

- [ ] **Step 5: Commit**

```bash
git add changelog.d/rule-families-version-fact.md
git commit -m "chore: #rule-families-version-fact changelog fragment

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review（plan 對 spec 覆蓋）

- 分組核心 families.py + 完整性 → Task 1。✅
- report.emit 分組 + OTHER catch-all + body==summary 不變量 → Task 2。✅
- cli 接線 → Task 3。✅
- README L271 marker / L269 去規則數 / L21 去 policy_version → Task 4。✅
- R-26 dogfood config + green/red → Task 5。✅
- MOC 連結（消 R-24 WARN）+ release SOP → Task 6。✅
- changelog fragment + 全綠 gate + openspec validate → Task 7。✅
- Non-goals 遵守：無 auto-fix、無 rule-count fact、無新 CLI flag、零 rule_id/label 變動。✅

**型別一致：** `emit(results, families=None)`、`families.family_of`/`ordered_families`/`OTHER`/`FAMILIES` 於 Task 1–3 一致；marker 值 `1.0.10`（動工時 VERSION）於 Task 4/5 一致。
