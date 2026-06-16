## ADDED Requirements

### Requirement: 納管 repo 必須宣告內容 tier
每個由 `paulsha-conventions` 納管的 repo MUST 在 `.paul-project.yml` 宣告 `tier`，值為 `shareable`、`work` 或 `personal` 之一。tier 表達該 repo 內容的預期可見性等級，是機密掃描規則用來決定強制程度的輸入。

#### Scenario: 合法 tier 通過 schema 驗證
- **WHEN** 對一個 `.paul-project.yml` 設定 `tier: shareable` 的 repo 跑 `python3 -m policy_check --repo .`
- **THEN** project-config schema 規則接受該檔案

#### Scenario: 非法 tier 未通過 schema 驗證
- **WHEN** 某 repo 的 `.paul-project.yml` 將 `tier` 設為 `{shareable, work, personal}` 以外的值
- **THEN** project-config schema 規則回報失敗

### Requirement: shareable repo 不得含雇主機敏標記
機密掃描規則（R-21）MUST 掃描 tracked 文字檔，比對雇主標記 denylist、個人絕對路徑與憑證模式。對宣告 `tier: shareable` 的 repo，命中必須使 policy check 失敗；對 `tier: work` 或 `tier: personal`，命中不得使檢查失敗。

#### Scenario: shareable repo 含雇主標記則失敗
- **WHEN** 一個 `tier: shareable` 的 repo 有一個 tracked 檔案引用 `BGW720`
- **THEN** R-21 回報失敗

#### Scenario: work repo 含相同標記不失敗
- **WHEN** 一個 `tier: work` 的 repo 有一個 tracked 檔案引用 `BGW720`
- **THEN** R-21 不回報失敗

#### Scenario: 乾淨的 shareable repo 通過
- **WHEN** 一個 `tier: shareable` 的 repo 不含任何 denylist 標記、個人路徑或憑證模式
- **THEN** R-21 回報通過

### Requirement: 機密掃描規則必須排除自身定義與 fixtures
由於 denylist 字串必然出現在規則實作、其測試 fixtures、以及被豁免的文件中，R-21 MUST 將這些路徑排除於掃描之外，使規則不會掃到自己。

#### Scenario: 規則不誤報自身原始碼
- **WHEN** R-21 在 `paulsha-conventions` repo（其 `r21_secret_scan.py` 與 fixtures 含 denylist 字串）內執行
- **THEN** R-21 對這些被豁免的路徑回報通過
