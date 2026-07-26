## MODIFIED Requirements

### Requirement: shareable repo 不得含雇主機敏標記
機密掃描規則（R-21）MUST 掃描所有 tier 的 tracked 文字檔，不得因 `tier !=
shareable` 跳過。偵測結果 MUST 分成 `structural`、`credential` 與 `marker`：
結構與憑證偵測器恆啟用；marker 則沿用 baseline 與 per-repo extend-only 設定，
且 `public_names` 只能抑制 marker。

R-21 MUST 依下列矩陣採用最嚴重 verdict：

| tier / visibility | structural 或 credential | marker | clean |
| --- | --- | --- | --- |
| `shareable` / 任意 | FAIL | FAIL | PASS |
| 非 shareable / `public` | FAIL | WARN | PASS |
| 非 shareable / `private` 或 `internal` | WARN | WARN | PASS |
| 非 shareable / `unknown` | FAIL | WARN | PASS |

#### Scenario: shareable repo 的任一命中皆失敗
- **WHEN** 一個 `tier: shareable` repo 命中 structural、credential 或 marker detector
- **THEN** R-21 回報 FAIL，不受 repository visibility 影響

#### Scenario: public work repo 的 credential 命中失敗
- **WHEN** 一個非 shareable 且 visibility 為 `public` 的 repo 命中 credential detector
- **THEN** R-21 回報 FAIL

#### Scenario: public work repo 的 marker 命中警告
- **WHEN** 一個非 shareable 且 visibility 為 `public` 的 repo只命中 marker detector
- **THEN** R-21 回報 WARN

#### Scenario: private 或 internal repo 的命中警告
- **WHEN** 一個非 shareable 且 visibility 為 `private` 或 `internal` 的 repo 命中任一 detector
- **THEN** R-21 回報 WARN

#### Scenario: unknown visibility 採保守判定
- **WHEN** 一個非 shareable 且 visibility 為 `unknown` 的 repo 命中 structural 或 credential detector
- **THEN** R-21 回報 FAIL，且訊息明示 visibility unknown

#### Scenario: 同時命中採最嚴重 verdict
- **WHEN** 同一 repo 同時命中會導致 WARN 與 FAIL 的 detector
- **THEN** R-21 回報 FAIL

#### Scenario: clean repo 通過
- **WHEN** repo 沒有任何 R-21 命中
- **THEN** R-21 回報 PASS；visibility unknown 時訊息仍明示 unknown

## ADDED Requirements

### Requirement: repository visibility 必須由既有執行上下文注入
`RuleContext` SHALL 提供 `repo_visibility`。GitHub MUST 從 event payload 的
`repository.visibility` 取得，缺值時依 `repository.private` boolean 正規化；
GitLab MUST 從 `CI_PROJECT_VISIBILITY` 取得。即使 GitHub event 沒有
`pull_request`，repository metadata 仍 MUST 保留。CLI SHALL 提供
`--repo-visibility {public,private,internal,unknown}`，優先序 MUST 為 provider
payload > CLI > `unknown`。Policy engine MUST NOT 為此呼叫 GitHub 或 GitLab API。

#### Scenario: GitHub event visibility 優先於 CLI
- **WHEN** GitHub event 提供 `repository.visibility=private`，CLI 同時注入 `public`
- **THEN** `RuleContext.repo_visibility` 為 `private`

#### Scenario: GitHub private boolean 作為 fallback
- **WHEN** GitHub event 缺少 `repository.visibility` 且 `repository.private=true`
- **THEN** `RuleContext.repo_visibility` 為 `private`

#### Scenario: 非 PR event 保留 repository metadata
- **WHEN** GitHub event 有 repository visibility 但沒有 `pull_request`
- **THEN** visibility 仍注入 `RuleContext`

#### Scenario: GitLab visibility 由環境注入
- **WHEN** GitLab MR pipeline 設定 `CI_PROJECT_VISIBILITY=internal`
- **THEN** `RuleContext.repo_visibility` 為 `internal`

#### Scenario: offline CLI 可顯式注入
- **WHEN** provider payload 沒有 visibility 且 CLI 傳入 `--repo-visibility public`
- **THEN** `RuleContext.repo_visibility` 為 `public`

#### Scenario: 無 authority 時 fail-closed 為 unknown
- **WHEN** provider payload 與 CLI 都沒有 visibility
- **THEN** `RuleContext.repo_visibility` 為 `unknown`

### Requirement: 機密掃描輸出不得洩漏命中內容
R-21 的 detail MUST 僅輸出 repo-relative `path:line`、detector 類別與受限命中筆數；
message MAY 輸出各 detector 的命中數，但 MUST NOT 輸出 matched value、原始 line
或 token 片段。

#### Scenario: credential 命中只輸出位置與類別
- **WHEN** tracked 檔含測試 credential 且 R-21 命中
- **THEN** detail 包含 repo-relative `path:line credential`，但不含 credential 內容

#### Scenario: marker 命中不輸出 marker 字串
- **WHEN** tracked 檔含 confidential marker 且 R-21 命中
- **THEN** detail 僅標示 `marker` 類別，不輸出 matched marker 或原始行
