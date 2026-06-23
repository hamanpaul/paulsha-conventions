# engine-version-attestation Specification

## Purpose
本 capability 閉合「repo 實際 pin 的 conventions 引擎版本 ⟷ 宣告的 `policy_version`」這條既有引擎（R-14/R-20 僅驗 intra-repo 自洽）結構性看不到的缺口——下游可升級引擎卻忘改版號（或反之）而全規則照樣 PASS，即 P0 跨 repo 漂移成因。R-23 掃描 workflow `uses:` 對 `conventions_engine.repo` 的外部 pin，比對其版本（tag `@vX.Y.Z`，或 SHA + 尾註 `# vX.Y.Z`）與 `policy_version`：不齊 FAIL、純 SHA 無註解 WARN、`./` 在地引用或未設則 NA。R-08 驗證 `conventions_engine` 設定 schema。
## Requirements
### Requirement: 引擎 pin 版本與 policy_version 對齊
R-23 MUST 掃描 `.github/workflows/*.yml` 中 `uses:` 指向 `conventions_engine.repo` 的引用。對每一**外部**引用，R-23 MUST 嘗試取出引擎版本：tag ref `@vX.Y.Z` 取其字面版本；SHA ref `@<40hex>` 且**同行尾註** `# vX.Y.Z` 取註解版本。取得版本後若 ≠ 專案 declared `policy_version` MUST 回報 FAIL。`./` 在地引用 MUST 跳過。

#### Scenario: tag pin 版本對齊
- **WHEN** 某 `uses:` 以 `@vX.Y.Z` 引用引擎且 `X.Y.Z` == declared `policy_version`
- **THEN** R-23 回報 PASS

#### Scenario: tag pin 版本不齊
- **WHEN** 某 `uses:` 以 `@vA` 引用引擎但 `A` ≠ declared `policy_version`
- **THEN** R-23 回報 FAIL

#### Scenario: SHA pin 帶版本註解且對齊
- **WHEN** 某 `uses:` 以 `@<sha>` 引用引擎且同行尾註 `# vX.Y.Z` 等於 declared `policy_version`
- **THEN** R-23 回報 PASS

#### Scenario: SHA pin 帶版本註解但不齊
- **WHEN** 某 `uses:` 以 `@<sha>` 引用引擎且尾註 `# vA` ≠ declared `policy_version`
- **THEN** R-23 回報 FAIL

### Requirement: 純 SHA pin 無版本註解時降級為 WARN
當引擎以純 SHA pin 引用且無 `# vX.Y.Z` 尾註時，R-23 無法離線反推版本，MUST 回報 WARN 並建議補上版本註解，MUST NOT 回報 FAIL。

#### Scenario: 純 SHA 無註解
- **WHEN** 某 `uses:` 以 `@<sha>` 引用引擎但無版本尾註
- **THEN** R-23 回報 WARN

### Requirement: 無外部引擎引用時 NA
當 `conventions_engine.repo` 未設、或 workflow 中查無指向該 repo 的外部 `uses:`（例如 canonical 自身以 `./` 在地引用）時，R-23 MUST 回報 PASS（不適用）。

#### Scenario: canonical 在地引用
- **WHEN** repo 僅以 `./` 在地引用引擎、無外部 pin
- **THEN** R-23 回報 PASS（NA）

#### Scenario: 未設 conventions_engine
- **WHEN** `.paul-project.yml` 未設 `conventions_engine.repo`
- **THEN** R-23 回報 PASS（NA）

### Requirement: R-23 支援豁免 label
R-23 MUST 在 PR 帶 `policy-exempt:engine-pin` label 時回報 SKIP。

#### Scenario: 豁免 label 生效
- **WHEN** PR 帶 `policy-exempt:engine-pin` label
- **THEN** R-23 回報 SKIP

### Requirement: conventions_engine 設定 schema 驗證
R-08 MUST 在 `.paul-project.yml` 出現 `conventions_engine` 時驗證其為 mapping，且 `conventions_engine.repo`（若存在）MUST 為字串；型別不符時 MUST 回報 FAIL。

#### Scenario: repo 非字串
- **WHEN** `conventions_engine.repo` 被設為非字串（如映射或陣列）
- **THEN** R-08 回報 FAIL

#### Scenario: 合法 repo 字串
- **WHEN** `conventions_engine.repo` 為字串
- **THEN** R-08 接受該檔

