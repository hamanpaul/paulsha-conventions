# canonical-doc-scope Specification

## Purpose
TBD - created by archiving change doc-rule-hardening. Update Purpose after archive.

## Requirements
### Requirement: 專案宣告 canonical documentation scope
專案設定 SHALL 支援 optional `doc_paths`，其值為 glob 字串陣列，用來宣告哪些檔案構成
repo 的 canonical documentation scope。當 `doc_paths` 未宣告時，documentation-related
rules SHALL 使用預設範圍 `README.md` 與 `docs/**`。

#### Scenario: 未宣告 doc_paths 時維持既有範圍
- **WHEN** `.paul-project.yml` 未宣告 `doc_paths`
- **THEN** documentation-related rules 仍以 `README.md` 與 `docs/**` 作為 canonical doc scope

#### Scenario: repo 可擴充 canonical docs 範圍
- **WHEN** `.paul-project.yml` 將 `CLAUDE.md` 與 `sw_core/assets/skill/SKILL.md` 納入 `doc_paths`
- **THEN** 使用 shared canonical doc scope 的規則會把這些路徑視為 in-scope docs

### Requirement: `R-18` 與 `R-22` SHALL 共用 canonical doc scope
`R-18` 與 `R-22` MUST 以同一份 `doc_paths` 設定決定 canonical doc scope。`R-18` SHALL 以此
判斷 code change 是否伴隨 docs touch；`R-22` SHALL 先由 `doc_paths` 取得候選文件，再套用
規則自身的 built-in exclusions。

#### Scenario: 自訂 canonical doc 會讓 `R-18` 視為 docs touch
- **WHEN** 專案把 `CLAUDE.md` 納入 `doc_paths`
- **AND** 某次 code change 同時修改 `CLAUDE.md`
- **THEN** `R-18` 將該變更視為有 docs update

#### Scenario: `R-22` 在 doc_paths 基礎上仍排除 spec 與 fixtures
- **WHEN** `doc_paths` 命中 `docs/superpowers/specs/example.md`
- **THEN** `R-22` 仍不掃描該檔，因其屬規則內建排除範圍

### Requirement: project-config schema 驗證 `doc_paths` 型別
R-08 project-config schema MUST 在 `.paul-project.yml` 出現 `doc_paths` 時，驗證其為字串陣列；
型別不符時 MUST 回報 FAIL。

#### Scenario: doc_paths 非字串陣列
- **WHEN** `.paul-project.yml` 將 `doc_paths` 設為字串或映射
- **THEN** R-08 回報 FAIL

#### Scenario: 合法的 doc_paths 陣列通過
- **WHEN** `.paul-project.yml` 的 `doc_paths` 為 glob 字串陣列
- **THEN** R-08 接受該檔案
