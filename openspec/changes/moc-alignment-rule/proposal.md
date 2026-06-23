## Why

brainstorm / openspec 都是**單一 feature 視角**，對整個專案全貌太片面。大型重構切成 10+ 個互相相依的 stage，做到一半可能發現某根本性改變需把前面「已完成」的 stage postpone 重做；若沒有持久的專案層地圖，新 session（或忘記此事的人）會把該 stage 當成已完成跳過 → 前後架構衝突。同理，專案的靜態操作脈絡（platform / vendor / toolchain / build / install / profiles）改了卻沒更新對應文件，agent 進場就讀到陳舊資訊。

需要一條**通用、platform-agnostic 的規則（R-24 moc-alignment）**，盯住 repo 宣告的 MOC（Map of Content）有沒有跟著本次變更同步。內容跟著專案走（留在各自 repo），paulsha 只提供這條 gate。

## What Changes

- 新增 **R-24（moc-alignment）**：repo 於 `.paul-project.yml` 宣告 `moc` 後生效（未宣告 → NA，opt-in）。三瓣：
  - **靜態鮮度（WARN，advisory）**：`moc.triggers` 命中的檔案在本次 diff 變動，但 `moc.static` 未在同 diff → WARN（啟發式提醒，比照 R-18）。
  - **動態連結懸空（diff-aware FAIL/WARN）**：`moc.map` 內的連結指向不存在的 spec / plan / openspec 產物 → 本次新破壞 FAIL、陳年 WARN（比照 R-22）。
  - **動態連結孤兒（WARN，永不 FAIL）**：存在 active openspec change / `docs/superpowers/plans/*` / `docs/superpowers/specs/*` 卻未被 `moc.map` 連結 → WARN（涵蓋 specs 但只提醒，舊專案導入不被打掉）。
- 規則邏輯純 git-level（`changed_files` + repo 檔案），**不依賴 GitHub/GitLab**——落地後可在任一平台 CI 執行。
- `.paul-project.yml` 新增 `moc` 區塊（`static` / `map` / `triggers`），R-08 擴充驗證。
- 新增豁免 label `policy-exempt:moc-alignment`。
- **非目標**：MOC「狀態語意對齊」（stage 宣稱 done 是否真 done）屬 L2 語意，由 advisory Copilot review 層處理，不納入本確定性規則。

## Capabilities

### New Capabilities
- `moc-alignment`: repo 宣告的 MOC（靜態脈絡檔 + 動態連結地圖）須與本次變更同步；R-24 確定性 gate（靜態鮮度 / 連結懸空 / 連結孤兒）＋ `moc` 設定與 R-08 驗證。

### Modified Capabilities
<!-- 無既有 spec 之 requirement 改變；R-24 為新引入規則。 -->

## Impact

- **規則引擎**：新增 `policy_check/rules/r24_moc_alignment.py`；`policy_check/rules/r08_policy_config_schema.py`（擴充驗 `moc`）。
- **設定**：`.paul-project.yml` 新增 `moc`（`static` / `map` / `triggers`）。
- **慣例檔／文件**：`CLAUDE.md`（claim-done 補 R-24、白名單加 `policy-exempt:moc-alignment`、新增「MOC 動態狀態對齊」advisory 段）、`README.md` 規則總覽、`CHANGELOG.md`。
- **測試**：R-24（靜態鮮度命中/未命中、連結懸空新破壞/陳年、孤兒、無 diff context 降級、NA、豁免）、R-08（`moc` schema）fixtures。
- **平台**：規則 platform-agnostic；於內部 GitLab 落地需引擎內部化（見 issue #20），但本案不依賴它。
- **release**：merge 當下 feature batch bump（PATCH，`flat` profile）。
