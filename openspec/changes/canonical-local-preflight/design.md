# Canonical local preflight design

## 1. CLI contract

- `policy-preflight` 應先解析輸入參數並建立執行上下文：repo、PR context、policy-only/offline 模式、step 過濾條件。
- `--pr` 與 `--offline` 互斥；`--pr` 呼叫 `gh pr view` 時，若無網路能力或命令缺少欄位可 fail-closed。
- effective head 必須等於目前 checkout branch，`origin/<base>` 必須存在且可與 HEAD
  建立 merge base，避免 policy engine 因缺 diff context 而把 changed-files 視為空集合。
- 非 `--policy-only` 時，依 `.paul-project.yml` 的 `preflight.steps` 遞增執行 step；每步驗證 argv 型別、cwd 限制、timeout，並列印命名結果。
- `--skip-tests` 只跳過 `kind: tests`；policy-only 跳過所有 `steps`，但保持 policy gate 本身與 resolver 檢核。

## 2. Offline contract

- `--offline` 禁止 `gh`、`git clone`、`git fetch`、network resolver 呼叫。
- 缺少 repo/sha/version artifact 時需列出缺漏明細並回 `FAIL`（exit 1）。
- repo-owned 命令仍由 repo authority 負責；preflight 僅回報「resolver 能力」與已驗證 artifact。

## 3. Engine & repo-owned steps schema

- `.paul-project.yml` 新增 `preflight` mapping，其中 `steps` 是 list of mapping。
- 每個 step 驗證：
  - `name` 為非空字串且不可重複。
  - `kind` 僅 `validation|tests`。
  - `argv` 非空 `list[str]`。
  - `cwd` / `when_path_exists` 必為 repo-relative，且非越界。
  - `timeout_seconds` 為正整數。
- unknown subkey 保持 lenient；已知欄位型別錯誤即 FAIL。

## 4. Pinned engine

- 本地 mode 需驗證 `policy_engine_ref` 與 reusable workflow uses ref 一致且為完整 SHA。
- source/SHA mode cache key 使用 `engine_repo@sha`，不得將「目前 checkout 位址」視為 cache hit。
- self-dogfood 只適用於未宣告外部 `conventions_engine.repo` 的 engine repo；下游 repo
  即使存在同名檔案，也不得繞過 pinned engine resolution。
- policy subprocess 以權限受限的暫存 GitHub event file 傳遞 PR metadata，不把 title/body
  放進 process argv；輸出只顯示 effective context 摘要。
