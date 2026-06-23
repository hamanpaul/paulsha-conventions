# agent-files-single-source Specification

## Purpose
本 capability 定義 agent 慣例檔的**單一真檔模型**：canonical `CLAUDE.md` + symlink 鏡像，取代四份 byte-identical 複本（業界視為 anti-pattern、且維護負擔重）。R-14 依 `.paul-project.yml` 的 `agent_files.mode`（`copy` 預設 / `symlink`）gate 行為——`symlink` 模式強制三鏡像檔為 resolve 到 canonical 的 symlink，divergent 複本／錯誤目標／canonical 自身為 symlink 即 FAIL；`copy` 維持既有四檔版本相等比對，讓下游可漸進遷移而不被打斷。R-08 驗證 `agent_files` 設定 schema。
## Requirements
### Requirement: agent 慣例檔以 canonical CLAUDE.md 為單一真檔
R-14 MUST 將 `CLAUDE.md` 視為唯一 canonical agent 慣例檔。當 `.paul-project.yml` 的 `agent_files.mode` 為 `symlink` 時：`CLAUDE.md` MUST 為一般檔（非 symlink）且其 `policy_version:` 宣告 MUST 等於專案 declared policy_version；`AGENTS.md`、`GEMINI.md`、`.github/copilot-instructions.md` MUST 各為 symlink 且 `resolve()` 指向 canonical `CLAUDE.md`。違反者 MUST 回報 FAIL。缺檔或斷鏈（`is_file()` 為假）交由 R-13 處理。R-14 MUST NOT 提供豁免 label（單一真檔為不可豁免之真相）。

#### Scenario: symlink 拓撲正確
- **WHEN** `mode=symlink`，三鏡像檔皆為 symlink 且 resolve 到 `CLAUDE.md`，canonical 為一般檔且版本相符
- **THEN** R-14 回報 PASS

#### Scenario: 鏡像檔為 divergent 複本
- **WHEN** `mode=symlink` 但某鏡像檔為一般檔（非 symlink）
- **THEN** R-14 回報 FAIL

#### Scenario: symlink 指向錯誤目標
- **WHEN** `mode=symlink` 但某鏡像檔之 symlink resolve 不到 canonical `CLAUDE.md`
- **THEN** R-14 回報 FAIL

#### Scenario: canonical 自身為 symlink
- **WHEN** `mode=symlink` 但 `CLAUDE.md` 本身為 symlink
- **THEN** R-14 回報 FAIL

### Requirement: copy 模式維持向後相容（預設）
當 `agent_files.mode` 為 `copy` 或未設時，R-14 MUST 維持既有行為：四份 agent 慣例檔各為一般檔，且各自 `policy_version:` 宣告 MUST 等於專案 declared policy_version；任一不符 MUST 回報 FAIL。缺檔交由 R-13 處理。

#### Scenario: 四檔版本一致
- **WHEN** `mode` 未設、四檔皆宣告相同 `policy_version` 且等於 declared
- **THEN** R-14 回報 PASS

#### Scenario: 版本漂移
- **WHEN** `mode=copy` 且某 agent 檔宣告的 `policy_version` 不等於 declared
- **THEN** R-14 回報 FAIL

### Requirement: agent_files 設定 schema 驗證
R-08 MUST 在 `.paul-project.yml` 出現 `agent_files` 時驗證其為 mapping，且 `agent_files.mode`（若存在）MUST ∈ {`symlink`, `copy`}；型別或列舉不符時 MUST 回報 FAIL。

#### Scenario: 非法 mode
- **WHEN** `agent_files.mode` 被設為列舉外的值（如 `link`）
- **THEN** R-08 回報 FAIL

#### Scenario: 合法 mode
- **WHEN** `agent_files.mode` 為 `symlink` 或 `copy`
- **THEN** R-08 接受該檔

