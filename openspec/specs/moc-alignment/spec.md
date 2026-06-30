# moc-alignment Specification

## Purpose
TBD - created by archiving change moc-alignment-rule. Update Purpose after archive.
## Requirements
### Requirement: moc 設定 schema 驗證
R-08 MUST 在 `.paul-project.yml` 出現 `moc` 時驗證其為 mapping；`moc.static`（若存在）MUST 為字串、`moc.map`（若存在）MUST 為字串、`moc.triggers`（若存在）MUST 為字串陣列；型別不符時 MUST 回報 FAIL。

#### Scenario: moc.triggers 非字串陣列
- **WHEN** `.paul-project.yml` 的 `moc.triggers` 被設為非 `list[str]`
- **THEN** R-08 回報 FAIL

#### Scenario: 合法 moc 區塊通過
- **WHEN** `moc` 為 mapping 且 `static` / `map` 為字串、`triggers` 為字串陣列
- **THEN** R-08 接受該檔

### Requirement: 未宣告 moc 時 R-24 不適用
R-24 MUST 在 `.paul-project.yml` 未宣告 `moc`（或 `moc` 為空）時回報 PASS（not applicable）。

#### Scenario: 未設 moc
- **WHEN** repo 的 `.paul-project.yml` 無 `moc` 區塊
- **THEN** R-24 回報 PASS（NA）

### Requirement: 靜態 MOC 鮮度
當 `moc.triggers` 設定存在時，R-24 MUST 檢查：若本次 `base..head` diff 中有檔案命中任一 `moc.triggers` glob，而 `moc.static` 宣告的檔案**未**在同一 diff 變動，MUST 回報 **WARN**（提醒同步靜態 MOC，不擋 merge）。無可解析 diff context（本地非 PR）時 MUST 略過此瓣或降為 WARN。

#### Scenario: trigger 檔變動但靜態 MOC 未同步
- **WHEN** 某命中 `moc.triggers` 的檔案在本次 diff 變動，且 `moc.static` 不在本次 diff
- **THEN** R-24 回報 WARN

#### Scenario: trigger 檔變動且靜態 MOC 一併更新
- **WHEN** 命中 trigger 的檔案與 `moc.static` 皆在本次 diff
- **THEN** R-24 不因鮮度回報

### Requirement: 動態地圖連結懸空（diff-aware）
R-24 MUST 委由 `doc-drift-core` 的 path-drift primitive 掃描 `moc.map` 宣告的地圖檔，對其中指向**受治理前綴**的連結／path token，於 head 無法解析到存在產物者回報懸空。受治理前綴 MUST 可參數化（預設沿用 `openspec/changes/**` 與 `docs/superpowers/{specs,plans}/**`），使本規則可在未採用該目錄結構的外部 repo 重用。嚴重度依 `base..head` diff 判定：本次變更才弄壞者 MUST 為 FAIL；base 與 head 皆不存在的陳年懸空 MUST 為 WARN。無 diff context 時 MUST 降為 WARN。

#### Scenario: 地圖連結指向本次刪除的產物
- **WHEN** `moc.map` 連結指向某受治理前綴下的產物，該產物在 base 存在、在 head 已被本次變更刪除
- **THEN** R-24 回報 FAIL

#### Scenario: 陳年懸空連結
- **WHEN** `moc.map` 連結指向的產物在 base 與 head 皆不存在
- **THEN** R-24 回報 WARN

#### Scenario: 自訂受治理前綴
- **WHEN** repo 設定自訂受治理前綴，`moc.map` 含一個指向該前綴下已刪產物的本次變更
- **THEN** R-24 依該前綴判定並回報 FAIL

### Requirement: 動態地圖連結孤兒
R-24 MUST 委由 `doc-drift-core` 的 coverage primitive 檢查存在於 repo 的**受治理產物**（預設：active openspec change `openspec/changes/<name>/` 不含 `archive/`、`docs/superpowers/plans/*` 與 `docs/superpowers/specs/*`；前綴 MUST 可參數化）是否皆被 `moc.map` 連結；未被任何連結涵蓋者 MUST 回報 **WARN**（提醒補入地圖）。此瓣 MUST NOT 回報 FAIL——使舊專案首次宣告 `moc` 時不因既有未連結產物被擋。

#### Scenario: 新 plan 未被地圖連結
- **WHEN** 存在一份 `docs/superpowers/plans/X.md`，而 `moc.map` 無任何指向它的連結
- **THEN** R-24 回報 WARN

#### Scenario: 所有產物皆被連結
- **WHEN** 每個 active openspec change 與 plan 在 `moc.map` 皆有對應連結
- **THEN** R-24 不因孤兒回報

### Requirement: R-24 支援豁免 label
R-24 MUST 在 PR 帶 `policy-exempt:moc-alignment` label 時回報 SKIP。

#### Scenario: 豁免 label 生效
- **WHEN** PR 帶 `policy-exempt:moc-alignment` label
- **THEN** R-24 回報 SKIP

### Requirement: platform-agnostic 判定
R-24 MUST 僅依 `ctx.changed_files`、`ctx.repo_root` 與 repo 內檔案進行判定，MUST NOT 依賴任何 GitHub / GitLab 平台專屬環境（事件 payload、CI 變數），以便同一規則在任一平台 CI 執行。

#### Scenario: 無平台事件來源仍可判定
- **WHEN** 在提供 `changed_files` 與 base ref 的脈絡下執行（不論來源平台）
- **THEN** R-24 依 diff 與 repo 檔案完成靜態鮮度與連結檢查

