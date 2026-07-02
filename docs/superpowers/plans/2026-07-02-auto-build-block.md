# auto_build 區塊（issue #30 提案 A）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `.paul-project.yml` 新增 optional `auto_build:` 區塊（LLM auto build 慣例欄位），R-08 做 lenient 形狀驗證，README 文件化。

**Architecture:** 完全比照既有 optional 區塊模式（`secret_scan`/`moc`）：`policy_check/rules/r08_policy_config_schema.py` 內加一段 `is not None` 驗證；engine 不消費、不執行該區塊（`policy_check/config.py` 不動）。未知 subkey 放行，欄位演進不需 engine release。

**Tech Stack:** Python 3 + PyYAML + pytest（現有 policy_check 引擎）。

**Spec:** `openspec/changes/auto-build-block/`（proposal/design/specs/tasks）＋ `docs/superpowers/specs/2026-07-02-auto-build-block-design.md`

---

### Task 1: R-08 `auto_build` 驗證（TDD）

**Files:**
- Modify: `tests/test_rule_r08_policy_config_schema.py`（檔尾追加）
- Modify: `policy_check/rules/r08_policy_config_schema.py`（`moc` 驗證段之後、最後 `return RuleResult(... PASS ...)` 之前插入）

- [x] **Step 1: Write the failing tests**

在 `tests/test_rule_r08_policy_config_schema.py` 檔尾追加（沿用檔內既有 `_write_config`/`_r08`/`_ctx` helpers 與頂部 `Status` import）：

```python
# ---- auto_build schema (issue #30 提案 A) ----

def test_r08_pass_when_auto_build_absent(tmp_path):
    # 回歸：未宣告 auto_build 行為不變
    repo = _write_config(tmp_path, "policy_profile: flat\npolicy_version: 1.0.11\n")
    result = _r08().check(_ctx(repo))
    assert result.status == Status.PASS


def test_r08_fail_when_auto_build_not_mapping(tmp_path):
    repo = _write_config(
        tmp_path,
        "policy_profile: flat\npolicy_version: 1.0.11\nauto_build: make image\n",
    )
    result = _r08().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "auto_build must be a mapping" in result.message


def test_r08_pass_on_empty_auto_build_mapping(tmp_path):
    repo = _write_config(
        tmp_path,
        "policy_profile: flat\npolicy_version: 1.0.11\nauto_build: {}\n",
    )
    result = _r08().check(_ctx(repo))
    assert result.status == Status.PASS


def test_r08_fail_when_auto_build_steps_is_str(tmp_path):
    repo = _write_config(
        tmp_path,
        "policy_profile: flat\npolicy_version: 1.0.11\nauto_build:\n  steps: make image\n",
    )
    result = _r08().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "auto_build.steps" in result.message


def test_r08_fail_when_auto_build_steps_mixed_types(tmp_path):
    repo = _write_config(
        tmp_path,
        "policy_profile: flat\npolicy_version: 1.0.11\nauto_build:\n  steps: [make, 42]\n",
    )
    result = _r08().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "auto_build.steps" in result.message


def test_r08_fail_when_auto_build_description_not_str(tmp_path):
    repo = _write_config(
        tmp_path,
        "policy_profile: flat\npolicy_version: 1.0.11\nauto_build:\n  description: [a, b]\n",
    )
    result = _r08().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "auto_build.description" in result.message


def test_r08_pass_valid_full_auto_build(tmp_path):
    cfg = (
        "policy_profile: flat\npolicy_version: 1.0.11\n"
        "auto_build:\n"
        "  description: build router firmware image in docker\n"
        '  setup: ["docker pull registry.example/fw-builder:latest"]\n'
        '  steps: ["docker run --rm -v $PWD:/src fw-builder make image"]\n'
        '  artifacts: ["out/*.img"]\n'
        '  verify: ["test -s out/firmware.img"]\n'
    )
    repo = _write_config(tmp_path, cfg)
    result = _r08().check(_ctx(repo))
    assert result.status == Status.PASS


def test_r08_pass_partial_auto_build(tmp_path):
    repo = _write_config(
        tmp_path,
        'policy_profile: flat\npolicy_version: 1.0.11\nauto_build:\n  steps: ["make"]\n',
    )
    result = _r08().check(_ctx(repo))
    assert result.status == Status.PASS


def test_r08_pass_auto_build_unknown_subkey(tmp_path):
    # 未知 subkey 放行：per-project 擴充與欄位演進不需 engine release
    repo = _write_config(
        tmp_path,
        "policy_profile: flat\npolicy_version: 1.0.11\n"
        'auto_build:\n  steps: ["make"]\n  timeout_minutes: 30\n',
    )
    result = _r08().check(_ctx(repo))
    assert result.status == Status.PASS


def test_r08_never_executes_auto_build_commands(tmp_path):
    # R-08 只驗形狀：steps 內命令是純資料，驗證過程不得產生副作用
    marker = tmp_path / "side-effect-marker"
    cfg = (
        "policy_profile: flat\npolicy_version: 1.0.11\n"
        f'auto_build:\n  steps: ["touch {marker}"]\n'
    )
    repo = _write_config(tmp_path, cfg)
    result = _r08().check(_ctx(repo))
    assert result.status == Status.PASS
    assert not marker.exists()
```

- [x] **Step 2: Run tests to verify they fail for the intended reason**

Run: `python3 -m pytest tests/test_rule_r08_policy_config_schema.py -q`

Expected: **恰好 4 failed**（`test_r08_fail_when_auto_build_not_mapping`、`test_r08_fail_when_auto_build_steps_is_str`、`test_r08_fail_when_auto_build_steps_mixed_types`、`test_r08_fail_when_auto_build_description_not_str`——現行 R-08 對未知 key `auto_build` 一律 PASS，故 `assert result.status == Status.FAIL` 失敗），其餘全部 passed（PASS 向測試在現行寬鬆行為下本來就過，為回歸證據）。

- [x] **Step 3: Write minimal implementation**

在 `policy_check/rules/r08_policy_config_schema.py` 的 `moc` 驗證段（`# 驗證 moc 區塊…` 至其結尾）之後、最終 `return RuleResult(rule_id=self.rule_id, status=Status.PASS, ...)` 之前插入：

```python
        # 驗證 auto_build 區塊（#30）：LLM auto build 慣例欄位。
        # 只驗形狀、永不執行其中命令；未知 subkey 一律放行（欄位演進不綁 engine release）。
        auto_build = data.get("auto_build")
        if auto_build is not None:
            if not isinstance(auto_build, dict):
                return RuleResult(rule_id=self.rule_id, status=Status.FAIL,
                                  message="auto_build must be a mapping")
            description = auto_build.get("description")
            if description is not None and not isinstance(description, str):
                return RuleResult(rule_id=self.rule_id, status=Status.FAIL,
                                  message="auto_build.description must be a string")
            for key in ("setup", "steps", "artifacts", "verify"):
                val = auto_build.get(key)
                if val is None:
                    continue
                if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
                    return RuleResult(rule_id=self.rule_id, status=Status.FAIL,
                                      message=f"auto_build.{key} must be a list of strings")
```

- [x] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_rule_r08_policy_config_schema.py -q`
Expected: 全部 passed。

再跑全套：`python3 -m pytest -q`
Expected: 全部 passed（其他規則不受影響）。

- [x] **Step 5: Commit**

```bash
git add tests/test_rule_r08_policy_config_schema.py policy_check/rules/r08_policy_config_schema.py
git commit -m "feat(r08): .paul-project.yml 新增 auto_build 區塊形狀驗證（#30 提案 A）" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Docs 同步（README + MOC + changelog fragment）

**Files:**
- Modify: `README.md`（`### 文件規則設定面…` 段之後、`## CHANGELOG fragment 模型（並行安全）` 之前插入新段）
- Modify: `docs/MOC.md`（Active changes / Plans / Specs 三處）
- Create: `changelog.d/30-auto-build-block.md`

- [x] **Step 1: README 新增 `auto_build` 段**

在 `## CHANGELOG fragment 模型（並行安全）` 標題行之前插入：

````markdown
### `auto_build` 區塊（LLM auto build 慣例，#30）

`.paul-project.yml` 可宣告 optional 的 `auto_build:` 區塊，承載 per-project build flow，
供 LLM auto build agent 冷讀即得「怎麼 build 這個專案」；不用 build 的 repo 整塊不寫、零負擔：

```yaml
auto_build:
  description: "router firmware image via docker build container"  # str：一句話 build 目標
  setup:                       # list[str]：環境準備命令
    - "docker pull registry.example/fw-builder:latest"
  steps:                       # list[str]：建置命令，依序執行
    - "docker run --rm -v $PWD:/src fw-builder make -C /src image"
  artifacts:                   # list[str]：預期產物 glob
    - "out/*.img"
  verify:                      # list[str]：建置成功驗證命令
    - "test -s out/firmware.img"
```

- **R-08 只驗形狀**：`auto_build` 須為 mapping；`description` str；`setup`/`steps`/`artifacts`/`verify`
  各為 list[str]。**未知 subkey 一律放行**（per-project 擴充與欄位演進不需 engine release），無必填 subkey。
- **engine 永不執行**：與 `cli`（R-16）、`cli_tree`（R-25）、`generated_facts`（R-26）等命令執行型
  設定不同，`auto_build` 內所有命令字串對 policy engine 而言是純資料，任何規則都不會執行它們。
  消費者是讀 config 的 LLM agent；執行與否及其安全審查由該 agent 的 Human-in-the-loop 流程負責。

````

- [x] **Step 2: MOC 三處更新**

`docs/MOC.md`：

1. `## Active openspec changes` 下把「（目前無 active change。）」換成：
   ```markdown
   - [auto-build-block（#30 提案 A）](../openspec/changes/auto-build-block/proposal.md) — 實作中
   ```
2. `## Plans` 清單頂部加：
   ```markdown
   - [auto-build-block（#30 提案 A）](superpowers/plans/2026-07-02-auto-build-block.md) — 實作中
   ```
3. `## Specs / designs` 清單頂部加：
   ```markdown
   - [auto-build-block design（#30 提案 A）](superpowers/specs/2026-07-02-auto-build-block-design.md) — 實作中
   ```

- [x] **Step 3: changelog fragment**

Create `changelog.d/30-auto-build-block.md`：

```markdown
---
type: feat
scope: policy-config
issue: 30
---
`.paul-project.yml` 新增 optional `auto_build:` 區塊（LLM auto build 慣例欄位：`description`/`setup`/`steps`/`artifacts`/`verify`），R-08 做 lenient 形狀驗證（未知 subkey 放行、engine 永不執行其中命令）。
```

- [x] **Step 4: Commit**

```bash
git add README.md docs/MOC.md changelog.d/30-auto-build-block.md
git commit -m "docs(readme): auto_build 區塊說明 + MOC 對齊 + changelog fragment（#30）" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: OpenSpec tasks 勾選 + Policy gate

**Files:**
- Modify: `openspec/changes/auto-build-block/tasks.md`（勾選已完成項）

- [x] **Step 1: 勾選 tasks.md**

把 `openspec/changes/auto-build-block/tasks.md` 內 1.1–3.3 已完成項的 `- [ ]` 改 `- [x]`（4.1/4.2 於 gate 通過後勾）。

- [x] **Step 2: Policy gate 實跑**

Run: `python3 -m pytest -q`
Expected: 全部 passed。

Run: `python3 -m policy_check --repo .`
Expected: 無任何 FAIL（R-24 因 MOC 已於 Task 2 對齊而過；R-09 因 fragment 存在而過）。

- [x] **Step 3: Commit（勾選與 gate 後殘餘變更）**

```bash
git add openspec/changes/auto-build-block/tasks.md
git commit -m "chore(openspec): 勾選 auto-build-block tasks 進度" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## 收尾（pipeline 後續 phase，非本計畫 task）

code review（含 fix 後 re-review）→ verification → openspec archive → 最終 policy gate →
codex adversarial review。PR 引用 issue 用「屬 #30 提案 A」非關閉形式 + `policy-exempt:issue-link`
（提案 B 未完不得 `Closes #30`）。push / 開 PR 需使用者明示。
