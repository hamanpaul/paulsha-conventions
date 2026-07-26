# R-21 visibility-coupling proposal

## Issue

`hamanpaul/paulsha-conventions#45`

## Why

讓 `R-21` 規則依據 repo visibility 進行分級判定，不再只侷限於 `tier=shareable`，並保留 `RuleContext` 不直接做環境 provider API 呼叫。

## What Changes

- `policy_check/pr_context.py`：擷取 GitHub/GitLab visibility。
- `policy_check/cli.py`：加入 `--repo-visibility`，供 local/offline CI parity。
- `policy_check/rules/base.py`：新增 `repo_visibility`。
- `policy_check/rules/r21_secret_scan.py`：新增 visibility coupling、credential 偵測器、輸出縮減。
- 測試：`tests/test_rule_r21_secret_scan.py`、`tests/test_pr_context_gitlab.py`、CLI visibility context tests。
