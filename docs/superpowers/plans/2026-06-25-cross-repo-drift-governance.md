# 跨 repo policy 漂移治理 Implementation Plan（#23）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 engine 側交付「read-only drift 偵測器 + org freshness gate runbook + 升版傳播 SOP」，結構性偵測並強制下游 repo 不落後 canonical `policy_version`，engine 不主動改下游。

**Architecture:** 新增 `policy_check/drift.py`（純比對邏輯可單測 + `gh` I/O 邊緣 + CLI 兩模式：`report` 唯讀 exit 0、`check` gate 落後 exit≠0）。強制不做成 R-xx 規則（被釘住的舊引擎無法強制自身過期），改由 org-level required workflow 跑 `drift check`；engine 只交付工具與文件。

**Tech Stack:** Python 3.12、`yaml.safe_load`、`subprocess` + `gh` CLI、`argparse`、pytest。

設計全文：`docs/superpowers/specs/2026-06-25-cross-repo-drift-governance-design.md`。
OpenSpec：`openspec/changes/cross-repo-drift-governance/`（proposal / design / specs / tasks）。

---

## File Structure

- Create: `policy_check/drift.py` — drift 工具（純邏輯 + I/O 邊緣 + CLI）。單一職責：版本漂移偵測。**不註冊為 rule**，不被 `registry.load_all()` 載入，不進 `python3 -m policy_check` FAIL 集合。
- Create: `tests/test_drift.py` — 純邏輯單測。
- Create: `docs/org-ruleset-runbook.md` — org 強制 runbook（含範例 workflow YAML）。
- Modify: `README.md` — 機制層子段 + 工具總覽提及 drift。
- Modify: `RELEASES.md` — 升版傳播 SOP 區塊。
- Modify: `docs/MOC.md` — 連結本案 openspec change / plan / runbook。
- Modify: `CHANGELOG.md` — `[Unreleased]` entry。

> 注意：**不要**把 `policy_check.drift` 加進 `.paul-project.yml` 的 `cli:` 區塊——那會觸發 R-16 要求把它的 `--help` 用 marker 同步進 README。drift 是 ops 工具，README 以散文提及即可。

---

## Task 1: drift 純邏輯（TDD）

**Files:**
- Test: `tests/test_drift.py`
- Create: `policy_check/drift.py`

- [ ] **Step 1: 寫 failing test**

`tests/test_drift.py`:

```python
from __future__ import annotations

import pytest

from policy_check import drift


# --- parse_version：-fix.N 完整排序 ---
def test_parse_version_absent_fix_is_zero():
    assert drift.parse_version("1.0.7") == (1, 0, 7, 0)


def test_parse_version_with_fix():
    assert drift.parse_version("1.0.7-fix.2") == (1, 0, 7, 2)


def test_no_suffix_sorts_below_fix1():
    assert drift.parse_version("1.0.7") < drift.parse_version("1.0.7-fix.1")


def test_fix_numeric_ordering():
    assert drift.parse_version("1.0.7-fix.2") > drift.parse_version("1.0.7-fix.1")


def test_parse_version_invalid_raises():
    with pytest.raises(ValueError):
        drift.parse_version("not-a-version")


# --- classify ---
def test_classify_behind():
    assert drift.classify("1.0.5", "1.0.7") == "behind"


def test_classify_current():
    assert drift.classify("1.0.7", "1.0.7") == "current"


def test_classify_ahead():
    assert drift.classify("1.0.8", "1.0.7") == "ahead"


def test_classify_hotfix_behind():
    # 落後但自洽的 hotfix 級漂移必須被抓
    assert drift.classify("1.0.7", "1.0.7-fix.2") == "behind"


def test_classify_unmanaged():
    assert drift.classify(None, "1.0.7") == "unmanaged"


# --- parse_policy_version ---
def test_parse_policy_version_extracts():
    text = "policy_profile: flat\npolicy_version: 1.0.7\n"
    assert drift.parse_policy_version(text) == "1.0.7"


def test_parse_policy_version_absent():
    assert drift.parse_policy_version("policy_profile: flat\n") is None


# --- format_report ---
def test_format_report_contains_rows_and_canonical():
    out = drift.format_report(
        [("alpha", "1.0.5", "behind"), ("beta", None, "unmanaged")], "1.0.7"
    )
    assert "canonical: 1.0.7" in out
    assert "behind" in out
    assert "unmanaged" in out
```

- [ ] **Step 2: 跑測試確認 RED**

Run: `python3 -m pytest tests/test_drift.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'policy_check.drift'`（正確失敗原因：模組未建）

- [ ] **Step 3: 寫最小實作（純邏輯）**

`policy_check/drift.py`:

```python
# policy_check/drift.py
"""Cross-repo policy_version drift detector (ops tool, NOT an R-xx rule)."""
from __future__ import annotations

import re

import yaml

CANONICAL_ORG = "hamanpaul"
CANONICAL_REPO = "paulsha-conventions"

_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-fix\.(\d+))?$")


def parse_version(ver: str) -> tuple[int, int, int, int]:
    """Parse MAJOR.MINOR.PATCH[-fix.N] into a comparable tuple.

    Absent -fix suffix sorts below -fix.1 (fix component = 0), so
    1.0.7 < 1.0.7-fix.1 < 1.0.7-fix.2.
    """
    m = _VERSION_RE.match(ver.strip())
    if not m:
        raise ValueError(f"invalid policy version: {ver!r}")
    major, minor, patch, fix = m.groups()
    return (int(major), int(minor), int(patch), int(fix) if fix is not None else 0)


def parse_policy_version(yaml_text: str) -> str | None:
    """Extract policy_version from .paul-project.yml content; None if absent."""
    try:
        data = yaml.safe_load(yaml_text) or {}
    except yaml.YAMLError:
        return None
    ver = data.get("policy_version")
    return str(ver) if ver is not None else None


def classify(repo_ver: str | None, canonical_ver: str) -> str:
    """Return one of: current | behind | ahead | unmanaged."""
    if repo_ver is None:
        return "unmanaged"
    r = parse_version(repo_ver)
    c = parse_version(canonical_ver)
    if r < c:
        return "behind"
    if r > c:
        return "ahead"
    return "current"


def format_report(rows: list[tuple[str, str | None, str]], canonical: str) -> str:
    """rows: list of (repo, policy_version_or_None, status)."""
    lines = [
        f"canonical: {canonical}  ({CANONICAL_ORG}/{CANONICAL_REPO}, latest tag)",
        "",
        f"{'REPO':<32} {'POLICY_VERSION':<16} STATUS",
    ]
    for repo, ver, status in rows:
        lines.append(f"{repo:<32} {(ver or '—'):<16} {status}")
    return "\n".join(lines)
```

- [ ] **Step 4: 跑測試確認 GREEN**

Run: `python3 -m pytest tests/test_drift.py -q`
Expected: PASS（12 passed）

- [ ] **Step 5: Commit**

```bash
git add tests/test_drift.py policy_check/drift.py
git commit -m "feat: #23 drift 純邏輯（版本排序/分類/報表）

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: drift I/O 邊緣 + CLI 兩模式

**Files:**
- Modify: `policy_check/drift.py`（append）

> I/O 邊緣依賴 `gh`，不寫單測（與 `pr_context.py` 同樣只在邊緣呼叫 subprocess）；以手動 smoke 佐證。

- [ ] **Step 1: append I/O 邊緣與 CLI**

在 `policy_check/drift.py` 末端（`format_report` 之後）加入：

```python
import argparse
import json
import subprocess
import sys
from pathlib import Path


def _gh(args: list[str]) -> str:
    return subprocess.check_output(["gh", *args], text=True, stderr=subprocess.DEVNULL)


def local_policy_version(path: str = ".") -> str | None:
    """Read policy_version from the .paul-project.yml at `path` (cwd repo)."""
    cfg = Path(path) / ".paul-project.yml"
    if not cfg.exists():
        return None
    return parse_policy_version(cfg.read_text(encoding="utf-8"))


def canonical_version_live(org: str = CANONICAL_ORG, repo: str = CANONICAL_REPO) -> str:
    """Latest release tag of canonical repo, e.g. 'v1.0.7' -> '1.0.7'."""
    out = _gh(["api", f"repos/{org}/{repo}/releases/latest"])
    tag = json.loads(out)["tag_name"]
    return tag.lstrip("v")


def list_managed_repos(org: str = CANONICAL_ORG) -> list[str]:
    out = _gh(["repo", "list", org, "--no-archived", "--limit", "200", "--json", "name"])
    return [r["name"] for r in json.loads(out)]


def fetch_policy_version(org: str, repo: str) -> str | None:
    """Fetch a repo's .paul-project.yml policy_version; None if file absent."""
    try:
        out = _gh([
            "api", f"repos/{org}/{repo}/contents/.paul-project.yml",
            "--header", "Accept: application/vnd.github.raw",
        ])
    except subprocess.CalledProcessError:
        return None
    return parse_policy_version(out)


def cmd_report(args: argparse.Namespace) -> int:
    canonical = canonical_version_live()
    rows: list[tuple[str, str | None, str]] = []
    for name in list_managed_repos(args.org):
        ver = fetch_policy_version(args.org, name)
        rows.append((name, ver, classify(ver, canonical)))
    if args.json:
        print(json.dumps(
            {"canonical": canonical,
             "repos": [{"repo": r, "policy_version": v, "status": s} for r, v, s in rows]},
            ensure_ascii=False,
        ))
    else:
        print(format_report(rows, canonical))
    return 0  # report 永遠 exit 0


def cmd_check(args: argparse.Namespace) -> int:
    canonical = args.against or canonical_version_live()
    repo_ver = local_policy_version(args.repo)
    status = classify(repo_ver, canonical)
    print(f"policy-drift: {status} (repo={repo_ver or '—'} canonical={canonical})")
    return 1 if status == "behind" else 0  # 只有 behind 擋 merge


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="policy-check-drift")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("report", help="List drift across an org (read-only, exit 0)")
    pr.add_argument("--org", default=CANONICAL_ORG)
    pr.add_argument("--json", action="store_true")
    pr.set_defaults(func=cmd_report)

    pc = sub.add_parser("check", help="Gate: fail (exit!=0) if THIS repo is behind canonical")
    pc.add_argument("--repo", default=".")
    pc.add_argument("--against", default=None, help="Override canonical version (skip gh)")
    pc.set_defaults(func=cmd_check)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 確認單測仍綠（未被 I/O 影響）**

Run: `python3 -m pytest tests/test_drift.py -q`
Expected: PASS（12 passed）

- [ ] **Step 3: check 模式以 `--against` 離線 smoke（不需 gh）**

Run: `cd /home/paul_chen/prj_pri/paulsha-conventions && python3 -m policy_check.drift check --against 1.0.7; echo "exit=$?"`
Expected: `policy-drift: current (repo=1.0.7 canonical=1.0.7)` 且 `exit=0`

Run: `python3 -m policy_check.drift check --against 1.0.9; echo "exit=$?"`
Expected: `policy-drift: behind ...` 且 `exit=1`

- [ ] **Step 4: report 模式 smoke（需 gh，唯讀）**

Run: `python3 -m policy_check.drift report --org hamanpaul`
Expected: 印出表格，本 repo 列為 `current`；行程 exit 0。若 `gh` 未登入則略過此步並於 PR 註明。

- [ ] **Step 5: Commit**

```bash
git add policy_check/drift.py
git commit -m "feat: #23 drift I/O 邊緣 + CLI（report 唯讀 / check gate）

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: org ruleset runbook

**Files:**
- Create: `docs/org-ruleset-runbook.md`

- [ ] **Step 1: 寫 runbook**

`docs/org-ruleset-runbook.md` 內容需含下列段落（完整可佐證）：

````markdown
# Org Ruleset Runbook — 跨 repo policy 強制（#23）

> 本文件操作需 `admin:org` 權限，**不在 repo CI 內自動套用**；engine 只交付步驟與範例。

## 目的
org 層 require 兩條 status check 才能 merge，涵蓋既有 repo、下游無法靜默停用：
- `Policy Check`：per-repo 自洽（R-14/R-20/R-23…，既有）。
- `Policy Freshness`：跑 `policy_check.drift check`，擋下「落後但自洽」的 repo（本案新增）。

## 前置
- `gh auth status` 為 org admin 帳號，且 token 具 `admin:org`。

## Step 1 — 建 org ruleset
UI：Org → Settings → Rules → Rulesets → New ruleset。target 全 org（或選定 repo），啟用：
- Require a pull request before merging。
- Block direct pushes to `main`（Restrict deletions / require PR）。
- Require status checks：`Policy Check`、`Policy Freshness`。

或 `gh api`（示意 payload）：
```bash
gh api -X POST /orgs/hamanpaul/rulesets \
  -f name='policy-enforcement' \
  -f target='branch' \
  -F enforcement='active' \
  -f 'conditions[ref_name][include][]=~DEFAULT_BRANCH' \
  -f 'rules[][type]=pull_request' \
  -f 'rules[][type]=required_status_checks' \
  -f 'rules[][parameters][required_status_checks][][context]=Policy Check' \
  -f 'rules[][parameters][required_status_checks][][context]=Policy Freshness'
```
（實際 payload 結構以 GitHub API 文件為準；UI 設定後可 `gh api /orgs/hamanpaul/rulesets` 匯出佐證。）

## Step 2 — org-level required workflow（Policy Freshness）
以 org required workflow / default setup 推下列 `policy-freshness.yml`，不靠各 repo 自行 include。
它 checkout canonical **最新**版（`ref: main`，org 控制、非各 repo 自釘）跑 `drift check`：

```yaml
name: Policy Freshness
on:
  pull_request:
jobs:
  freshness:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4               # 下游 repo（含其 .paul-project.yml）
      - uses: actions/checkout@v4               # canonical engine（最新）
        with:
          repository: hamanpaul/paulsha-conventions
          ref: main
          path: .engine
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -e ./.engine
      - run: python3 -m policy_check.drift check --repo .
        env:
          GH_TOKEN: ${{ github.token }}
```

## Step 3 — 驗證（下游落後實驗）
1. 在一個 `policy_version` 落後 canonical 的下游 repo 開 PR。
2. `Policy Freshness` 跑 `drift check` → 判 `behind` → exit≠0 → required check 失敗 → **merge 被擋**。
3. 把該 repo 依「升版傳播 SOP」帶到 canonical 後重跑 → 通過。
4. 佐證：PR checks 截圖 或 `gh api /orgs/hamanpaul/rulesets`。

## 與既有機制並存
org freshness gate 與 `reusable-policy-check.yml` 的 R-15 / R-23 dual-pin 並存、職責不同：
per-repo Policy Check 驗「在你釘的版本下自洽嗎」；freshness gate 驗「你釘的版本還是不是最新」。

## Non-goals
- 不改規則引擎邏輯。
- GitLab 發行另見 #20。
````

- [ ] **Step 2: Commit**

```bash
git add docs/org-ruleset-runbook.md
git commit -m "docs: #23 org ruleset runbook（Policy Freshness required workflow）

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: 升版傳播 SOP（README + RELEASES）

**Files:**
- Modify: `README.md`（「Doc-alignment governance」段附近 + 工具總覽）
- Modify: `RELEASES.md`（開頭說明段）

- [ ] **Step 1: 讀現況定位插入點**

Run: `grep -n "Doc-alignment governance\|## " README.md | head -40`
Run: `sed -n '1,6p' RELEASES.md`

- [ ] **Step 2: README 新增機制層子段**

在「## Doc-alignment governance（三層）」段之後新增：

```markdown
### 跨 repo 升版傳播（機制層，#23）

確定性的三層 doc-alignment 是 **intra-repo**；跨 repo 的 `policy_version` 漂移由本機制層治理：

- **強制（擋）**：org ruleset 的 `Policy Freshness` required workflow 跑 `python3 -m policy_check.drift check`，落後 canonical 的 repo PR 無法 merge。設定見 [`docs/org-ruleset-runbook.md`](docs/org-ruleset-runbook.md)。
- **偵測（點名）**：`python3 -m policy_check.drift report --org hamanpaul` 唯讀列出各 repo 版本與漂移狀態。
- **修復（升）**：落後 repo 由其自身 agent 依 [RELEASES.md](RELEASES.md) 的「升版傳播 SOP」自助升版。engine 不主動改下游。
```

並在工具/規則總覽處加一行：

```markdown
- `policy_check.drift`（ops 工具，非 gate 規則）：跨 repo `policy_version` 漂移 `report`（唯讀）/ `check`（gate）。
```

- [ ] **Step 3: RELEASES.md 擴成明確 SOP**

把開頭「下游 repo 的 `POLICY_ENGINE_REF` 釘選 SHA 時…升版傳播 PR 必須同時更新…」那句下方，新增：

```markdown
## 升版傳播 SOP（下游 repo 自助）

canonical bump 後，落後的下游 repo 由**其自身 agent** 依序升版（drift report 會點名哪些 repo 落後）：

1. 查本表取目標 `policy_version` 與對應 engine SHA。
2. 改 `.paul-project.yml` 的 `policy_version`。
3. re-pin workflow 的 `policy_engine_ref` 為新 SHA，並補 `# vX.Y.Z` 尾註（R-23）。
4. canonical `CLAUDE.md` 有變則更新（AGENTS.md / GEMINI.md / copilot-instructions.md 為 symlink，自動跟隨）。
5. `python3 -m pytest -q` 與 `python3 -m policy_check --repo .` 全綠。
6. 開 PR（hamanpaul → zh-tw），body 寫 `Closes #N`（若有對應 issue）。
```

- [ ] **Step 4: Commit**

```bash
git add README.md RELEASES.md
git commit -m "docs: #23 升版傳播 SOP（README 機制層 + RELEASES 流程）

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: 文件對齊與收尾

**Files:**
- Modify: `CHANGELOG.md`、`docs/MOC.md`

- [ ] **Step 1: CHANGELOG [Unreleased] 補 entry**

Run: `grep -n "Unreleased" CHANGELOG.md | head`
在 `[Unreleased]` 下新增（沿用既有格式 Added 區）：

```markdown
- #23 跨 repo policy 漂移治理：新增 `policy_check/drift.py`（`report` 唯讀 / `check` gate，版本比較含 `-fix.N` 完整排序）、`docs/org-ruleset-runbook.md`（org `Policy Freshness` required workflow）、README 機制層子段與 RELEASES 升版傳播 SOP。engine 不主動改下游。
```

- [ ] **Step 2: docs/MOC.md 連結本案產物（避免 R-24 orphan WARN）**

Run: `cat docs/MOC.md`
把下列三個產物連進 `moc.map`（依該檔現有格式）：
- `openspec/changes/cross-repo-drift-governance/`（active change）
- `docs/superpowers/plans/2026-06-25-cross-repo-drift-governance.md`
- `docs/org-ruleset-runbook.md`

- [ ] **Step 3: 全測試綠**

Run: `python3 -m pytest -q`
Expected: 全 PASS（含新 `tests/test_drift.py`）

- [ ] **Step 4: policy_check 自檢無 failure**

Run: `python3 -m policy_check --repo .`
Expected: 無 FAIL（R-24 orphan WARN 應因 Step 2 連結而消除；殘留純 WARN 可接受）

- [ ] **Step 5: Commit**

```bash
git add CHANGELOG.md docs/MOC.md
git commit -m "docs: #23 CHANGELOG + MOC 連結本案產物

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 6: requesting-code-review（Phase 7）**

依 `superpowers:requesting-code-review` 對整支 feature 分支請 review；依 `receiving-code-review` 處理每個 finding，每次 fix 後 re-review。

---

## Self-Review（plan vs spec）

- **Spec coverage**：spec 七條 requirement 對應——report（T2 cmd_report）、check gate（T2 cmd_check）、`-fix.N` 排序（T1 parse_version）、unmanaged 跳過（T1 classify + T2 check exit 0）、engine 不改下游（全工具唯讀，無 commit/PR 下游）、org runbook（T3）、升版傳播 SOP（T4）。皆有任務。
- **Placeholder scan**：無 TBD/TODO；所有 code step 附完整 code。
- **Type consistency**：`parse_version`→tuple[int×4]、`classify(str|None,str)->str`、`format_report(list[tuple],str)->str`、`local_policy_version`/`fetch_policy_version`->`str|None`、CLI `cmd_report`/`cmd_check(args)->int`，前後一致。
