# cross-repo-drift-governance Specification

## Purpose
偵測並強制下游 repo 的 `policy_version` 不落後 canonical：提供唯讀的 drift 報表（operator 儀表板）與可 gate 的 freshness 檢查（org required workflow），搭配 org ruleset 強制與升版傳播 SOP。engine 只強制＋偵測＋文件，不主動改下游內容。
## Requirements
### Requirement: Drift 報表模式（report）

`policy_check.drift` SHALL 提供唯讀的 `report` 子命令，列舉指定 org（預設 `hamanpaul`）內每個含政策設定檔（`.project-policy.yml` 或 `.paul-project.yml`）的 repo，對 live canonical `policy_version` 分類為 `current` / `behind` / `ahead` / `unmanaged` 並輸出。單一 repo 版本無法解析時標 `invalid` 而不中斷整份報表。報表模式 MUST 永遠以 exit code 0 結束，且 MUST NOT 修改任何 repo 內容。

#### Scenario: 列出落後與最新的 repo

- **WHEN** operator 執行 `python3 -m policy_check.drift report --org hamanpaul`
- **THEN** 輸出每個 managed repo 一列（repo ｜ policy_version ｜ status），落後 canonical 者標 `behind`、相符者標 `current`
- **AND** 行程以 exit code 0 結束

#### Scenario: 單一壞版本不致整份報表崩潰

- **WHEN** 某 repo 的 `policy_version` 無法解析
- **THEN** 該列標 `invalid`，其餘 repo 仍正常列出，行程 exit code 0

#### Scenario: JSON 輸出供機器消費

- **WHEN** operator 加上 `--json`
- **THEN** 輸出結構化 JSON（含 canonical 版本與各 repo 分類），exit code 0

### Requirement: Freshness gate 模式（check）

`policy_check.drift` SHALL 提供 `check` 子命令，讀取**當前工作目錄** repo 的 `policy_version` 並對 live canonical（或 `--against` 指定值）比對。當分類為 `behind` 或版本無法解析（`invalid`）時，行程 MUST 以非 0 exit code 結束以擋下 merge（fail-closed）；`current` / `ahead` / `unmanaged` 時 MUST 以 exit code 0 結束。check 模式 MUST NOT 修改任何 repo 內容。

#### Scenario: 落後但自洽的 repo 被擋下

- **WHEN** 某 repo `policy_version` 為 `1.0.5`、canonical 為 `1.0.7`，且該 repo 在自己釘的版本下 R-14/R-20/R-23 皆自洽
- **AND** org required workflow 在其 CI 執行 `python3 -m policy_check.drift check`
- **THEN** drift 判其為 `behind` 並以非 0 exit code 結束，使 required check 失敗、merge 被擋

#### Scenario: 最新的 repo 通過

- **WHEN** 某 repo `policy_version` 等於 canonical
- **THEN** `drift check` 以 exit code 0 結束，required check 通過

### Requirement: 版本比較涵蓋 `-fix.N` 排序

drift 的版本比較 SHALL 解析 `MAJOR.MINOR.PATCH[-fix.N]` 並以完整順序比較，其中**無 `-fix` 尾註者排序低於 `-fix.1`**，且 `-fix.N` 之間依數值排序。MUST NOT 在比較時摺疊或忽略 `-fix.N` 尾段。

#### Scenario: hotfix 級漂移被偵測

- **WHEN** canonical 為 `1.0.7-fix.2`、repo 為 `1.0.7`
- **THEN** repo 被判為 `behind`（非 `current`）

#### Scenario: 無尾註低於 fix.1

- **WHEN** 比較 `1.0.7` 與 `1.0.7-fix.1`
- **THEN** `1.0.7` 排序低於 `1.0.7-fix.1`

### Requirement: 非受管 repo 跳過

當目標 repo 無政策設定檔（`.project-policy.yml` 或 `.paul-project.yml`）或其中無 `policy_version` 時，drift SHALL 分類為 `unmanaged`，report 模式 MUST 標示 `unmanaged` 而不視為漂移，check 模式 MUST 以 exit code 0 結束（不擋 merge）。設定檔名 MUST 與引擎 `config` 接受的兩種名稱一致，避免用 legacy 檔名的 repo 被誤判為 `unmanaged` 而靜默過 gate。

#### Scenario: 非政策管轄 repo 不誤傷

- **WHEN** 某 repo 無政策設定檔
- **THEN** report 標其為 `unmanaged`，check 模式對其 exit code 0

#### Scenario: legacy 檔名仍被辨識

- **WHEN** 某 repo 以 `.project-policy.yml` 宣告 `policy_version` 且落後 canonical
- **THEN** drift 判其 `behind`（不得因檔名而誤判 `unmanaged`）

### Requirement: engine 不主動改下游

本能力的所有 engine 側交付（drift 工具、文件）SHALL 為唯讀或純文件，MUST NOT clone、改檔或替下游 repo 開 PR。落後 repo 的修復由其自身 agent 依升版傳播 SOP 執行。

#### Scenario: 工具不 mutate 下游

- **WHEN** 執行 `drift report` 或 `drift check`
- **THEN** 不對任何下游 repo 產生 commit、PR 或檔案變更

### Requirement: org 強制 runbook

本能力 SHALL 交付 `docs/org-ruleset-runbook.md`，文件化以 org ruleset require `Policy Check` 與新增 `Policy Freshness`（跑 `drift check`）兩條 status check、require PR、禁直推 `main`，並含範例 workflow YAML 與「下游落後實驗」驗證步驟。runbook MUST 標示其操作需 `admin:org` 且不在 repo CI 內自動套用。

#### Scenario: runbook 提供可佐證的強制步驟

- **WHEN** 具 `admin:org` 的使用者依 runbook 操作
- **THEN** 能建立涵蓋既有 repo 的 org ruleset，並透過「下游落後實驗」確認落後 repo 的 PR 被擋下

### Requirement: 升版傳播 SOP

本能力 SHALL 於 `README.md`（機制層子段）與 `RELEASES.md`（傳播流程）文件化下游 repo 自助升版步驟：查 `RELEASES.md` 取 canonical 版本/SHA → 改 `.paul-project.yml` `policy_version` → re-pin engine SHA + `# vX.Y.Z` 尾註 → 更新 canonical agent 檔（symlink 自動跟隨）→ 測試與 `policy_check` 全綠 → 開 PR。

#### Scenario: 下游 agent 依 SOP 升版

- **WHEN** drift report 指出某 repo `behind`
- **THEN** 該 repo 的 agent 能依 SOP 將其 `policy_version`、engine pin 與 agent 檔帶到 canonical 並通過所有 gate
