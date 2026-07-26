# R-21 visibility-coupling design

## Context inputs

`RuleContext` carries `repo_visibility`。優先序：

1. Provider payload（GitHub/GitLab）
2. CLI 覆寫（`--repo-visibility`）
3. `unknown`

## R-21 verdict

`R-21` 仍掃描所有 tracked text 檔；命中分類：

- `structural`：`/home/<user>/...`、`BEGIN PRIVATE KEY`
- `credential`：AWS access-key 測試 token、GitHub token 前綴測試 token
- `marker`：`secret_scan` markers（baseline + repo extend）

`shareable` tier 一律 fail；其餘 tier 依 visibility 套用表格化規則。

## reporting

`detail` 僅輸出 `path:line detector`；不得輸出原始 line 或 token 值。
