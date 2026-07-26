# secret-scan Specification

## Purpose
TBD - created by archiving change 2026-06-14-account-visibility-and-secret-scan. Update Purpose after archive.
## Requirements
### Requirement: 納管 repo 必須宣告內容 tier
每個由 `paulsha-conventions` 納管的 repo MUST 在 `.paul-project.yml` 宣告 `tier`，值為 `shareable`、`work` 或 `personal` 之一。tier 表達該 repo 內容的預期可見性等級，是機密掃描規則用來決定強制程度的輸入。

#### Scenario: 合法 tier 通過 schema 驗證
- **WHEN** 對一個 `.paul-project.yml` 設定 `tier: shareable` 的 repo 跑 `python3 -m policy_check --repo .`
- **THEN** project-config schema 規則接受該檔案

#### Scenario: 非法 tier 未通過 schema 驗證
- **WHEN** 某 repo 的 `.paul-project.yml` 將 `tier` 設為 `{shareable, work, personal}` 以外的值
- **THEN** project-config schema 規則回報失敗

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

### Requirement: 機密掃描規則必須排除自身定義與 fixtures
由於 denylist 字串必然出現在規則實作、其測試 fixtures、以及被豁免的文件中，R-21 MUST 將這些路徑排除於掃描之外，使規則不會掃到自己。

#### Scenario: 規則不誤報自身原始碼
- **WHEN** R-21 在 `paulsha-conventions` repo（其 `r21_secret_scan.py` 與 fixtures 含 denylist 字串）內執行
- **THEN** R-21 對這些被豁免的路徑回報通過

### Requirement: 機密標記清單必須由設定驅動且可疊加
R-21 的 confidential marker 與 public-name 清單 MUST 來自引擎內附的 baseline 資料檔（非寫死於規則原始碼），且每個 repo 可於 `.paul-project.yml` 的 `secret_scan.markers` / `secret_scan.public_names` 疊加自身項目。疊加為 extend-only：repo 不能移除 baseline 的 marker；要在單一 repo 壓制某 marker，須將其加入該 repo 的 `public_names`。

#### Scenario: 中央減敏移除 baseline marker
- **WHEN** 將某 token 從 baseline 資料檔的 `markers` 移除（或加入 `public_names`）後重發引擎
- **THEN** 套用該版引擎的 shareable repo 不再因該 token 失敗

#### Scenario: per-repo 疊加 marker
- **WHEN** 某 `tier: shareable` repo 在 `.paul-project.yml` 的 `secret_scan.markers` 增補一個自身機密 token，且某 tracked 檔含該 token
- **THEN** R-21 對該 repo 回報失敗（baseline 未含該 token）

#### Scenario: per-repo public_names 局部壓制
- **WHEN** 某 `tier: shareable` repo 在 `secret_scan.public_names` 加入一個原本會命中的 token
- **THEN** R-21 不因該 token 使該 repo 失敗

### Requirement: project-config schema 必須驗證 secret_scan 標記欄位
project-config schema（R-08）MUST 接受 `secret_scan` 物件下的 optional `markers` 與 `public_names`（皆為 `list[str]`），與既有 `allow` 並存；元素非字串時回報失敗。

#### Scenario: 合法 secret_scan 標記欄位通過
- **WHEN** `.paul-project.yml` 設 `secret_scan: { markers: ["FOO123"], public_names: ["broadcom"] }`
- **THEN** R-08 接受該檔案

#### Scenario: 非法 secret_scan 標記欄位失敗
- **WHEN** `.paul-project.yml` 將 `secret_scan.markers` 設為非 list-of-str（如字串或含非字串元素）
- **THEN** R-08 回報失敗

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

