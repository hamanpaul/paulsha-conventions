## MODIFIED Requirements

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
