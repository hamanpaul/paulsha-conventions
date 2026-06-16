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
機密掃描規則（R-21）MUST 掃描 tracked 文字檔。偵測分兩層：(a) **結構偵測器**（個人絕對路徑、憑證模式）恆啟用、不可由 repo 關閉；(b) **marker token** 由設定驅動。marker 與 public-name 清單來自引擎 baseline 資料檔，per-repo 的 `.paul-project.yml` 可**疊加**（extend-only，不可移除 baseline marker）。對宣告 `tier: shareable` 的 repo，命中（結構偵測器，或 marker token 且該 token 不在 public-name 清單）必須使 policy check 失敗；對 `tier: work` 或 `tier: personal`，命中不得使檢查失敗。

#### Scenario: shareable repo 含 marker 則失敗
- **WHEN** 一個 `tier: shareable` 的 repo 有一個 tracked 檔案引用 baseline `markers` 中的 token（如 `BGW720`）
- **THEN** R-21 回報失敗

#### Scenario: 公開技術名不使 shareable repo 失敗
- **WHEN** 一個 `tier: shareable` 的 repo 含 baseline `public_names` 中的 token（如 `broadcom`、`prplOS`）且無其他 marker 命中
- **THEN** R-21 回報通過

#### Scenario: work repo 含相同 marker 不失敗
- **WHEN** 一個 `tier: work` 的 repo 有一個 tracked 檔案引用 `BGW720`
- **THEN** R-21 不回報失敗

#### Scenario: 結構偵測器恆啟用
- **WHEN** 一個 `tier: shareable` 的 repo 即使 effective `markers` 為空，仍有檔案含 `/home/<user>/` 路徑或 `BEGIN PRIVATE KEY`
- **THEN** R-21 回報失敗

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

