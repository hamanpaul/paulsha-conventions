# Proposal: auto-build-block

## Why

`.paul-project.yml` 目前只承載 policy 設定；issue #30 需要一份 repo 內、機器可讀的
「怎麼 build 這個專案」宣告，供 LLM auto build agent 讀取。現況下每個專案的 build flow
散落在人腦與 wiki，agent 每次都要重新摸索。

## What Changes

- `.paul-project.yml` 新增 **optional** 頂層區塊 `auto_build:`（不用 build 的 repo 不寫，零負擔）。
- 慣例 subkey：`description`（str）、`setup` / `steps` / `artifacts` / `verify`（list[str]）。
- R-08 新增 `auto_build` 形狀驗證：mapping + 已知 subkey 型別檢查；**未知 subkey 放行**
  （欄位演進不需 engine release）；無必填 subkey。
- 明確界線：engine 只驗形狀，**永不執行** `auto_build` 內的命令（與 R-16/R-25/R-26
  命令執行型規則區隔）。
- `README.md` 新增 `auto_build` 區塊說明（R-18 docs 同步）。
- 不動 `policy_check/config.py`（engine 不消費該區塊）；本 repo 自身不寫 `auto_build`。

範圍註記：issue #30 的提案 B（project-scan 注入機制）產物在本 repo 之外，不在本 change；
PR 引用 #30 採非關閉形式 + `policy-exempt:issue-link`。

## Capabilities

### New Capabilities
- `auto-build-config`: `.paul-project.yml` 的 `auto_build` 區塊慣例（欄位語意、optional 性質、
  消費者為 LLM agent）及其 R-08 形狀驗證與「永不執行」邊界。

### Modified Capabilities

（無——R-08 對既有 key 的行為不變；本 change 只新增 optional 區塊的驗證，未改任何既有 requirement。）

## Impact

- `policy_check/rules/r08_policy_config_schema.py`：新增一段 optional 區塊驗證（仿 `moc` 段）。
- `tests/test_rule_r08_policy_config_schema.py`：新增 pass/fail 測試。
- `README.md`：新增設定面說明段落。
- `changelog.d/30-auto-build-block.md`：feat fragment。
- 下游 repo：無影響（未宣告即維持既有行為；舊 engine 對新區塊本就放行）。
