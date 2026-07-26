# Canonical local CI-parity preflight proposal

## Issue

`hamanpaul/paulsha-conventions#46`

## Why

建立本 repo 的 `policy-preflight` canonical CLI，並以 repo-owned config 與 engine metadata 驗證
PR context、policy gate 與測試/OpenSpec 步驟，以提升 local-parity 預檢成功率。

## What Changes

- 新增 `policy_check` 本地 preflight entrypoint `policy-preflight`：
  - `policy-preflight`
  - `python3 -m policy_check.preflight`
- 新增 `--repo`, `--pr`, `--pr-title`, `--pr-body-file`, `--pr-labels`,
  `--base`, `--head`, `--skip-tests`, `--policy-only`, `--offline`,
  `--cache-dir` 參數支援。
- 新增 `.paul-project.yml` `preflight` section schema 驗證。
- 以 repo-owned commands 與 resolver metadata 逐步執行 `preflight` 步驟，輸出
  `PASS/FAIL/SKIP` + duration + effective engine。
- 以本 issue 可追蹤測試與 OpenSpec 變更支撐功能契約。

## Out of scope

- `custom-skills` wrapper（`preflight-ci`）留待下游 phase 依 plan 處理。
- 不新增或變更現有 CI provider 介面（pytest、Gradle、Make 等）執行邏輯，只在本地 preflight
  以 config 型資料描述需跑步驟。
