## Why

`policy_version` bump 時，下游 repo（`.github`、`new-project-template`、其他 `hamanpaul/*`）目前靠**手動 per-repo PR** 追上 canonical。R-14 / R-20 / R-23 只驗**單 repo 自洽**，看不到「某 repo 落後 canonical」這種**跨 repo 漂移**；一旦有人忘記同步，漂移會復發且 gate 不報。需要把「P0 跨 repo 漂移」從「手動治好」變成「結構性治好」。

## What Changes

- 新增 **drift 偵測器** `policy_check/drift.py`，兩種模式：
  - **report**（operator 唯讀儀表板，永遠 exit 0）：列舉 `hamanpaul/*` 各 managed repo 的 `policy_version`，對 live canonical 分類（`current` / `behind` / `ahead` / `unmanaged`）並印表。
  - **check**（org required workflow 當 gate）：比當前 repo 的 `policy_version` 對 live canonical，`behind` → **exit≠0 擋 merge**。
- 版本比較採**完整 `MAJOR.MINOR.PATCH[-fix.N]` 排序**（無尾註 < `-fix.1` < `-fix.2`），不摺疊 hotfix 漂移。
- 新增 **org ruleset / required-workflow runbook**（`docs/org-ruleset-runbook.md`）：文件化以 org ruleset require `Policy Check` + 新增 `Policy Freshness`（跑 `drift check`）兩條 status check、require PR、禁直推 `main`，涵蓋既有 repo 且下游無法靜默停用。含範例 workflow YAML 與「下游落後實驗」驗證步驟。
- 新增 **升版傳播 SOP**（`README.md` 機制層子段 + `RELEASES.md` 傳播流程）：描述**下游 repo 自己的 agent** 如何自助升版。
- **非目標 / 不做**：engine **不主動 mutate 下游**（不 clone／改檔／替下游開 PR）；不新增 R-xx 規則（強制住在 org 層 required workflow，理由見 design）；GitLab 發行另見 #20。

## Capabilities

### New Capabilities
- `cross-repo-drift-governance`: 偵測並強制下游 repo 的 `policy_version` 不落後 canonical——drift 工具（report 唯讀 / check gate）的行為契約，搭配 org required workflow 強制與升版傳播 SOP。engine 只強制＋偵測＋文件，不改下游內容。

### Modified Capabilities
<!-- 無既有 spec 之 requirement 改變；本案為新引入能力，不更動 R-14/R-20/R-23 等既有規則行為。 -->

## Impact

- **新增工具**：`policy_check/drift.py`（純邏輯 + gh I/O 邊緣）。
- **測試**：`tests/test_drift.py`（`-fix.N` 完整排序、落後但自洽判 behind、報表輸出）。
- **文件**：`docs/org-ruleset-runbook.md`（新）、`README.md`（機制層子段 + 規則／工具總覽）、`RELEASES.md`（傳播 SOP）、`docs/MOC.md`（連結本案產物，避免 R-24 orphan WARN）、`CHANGELOG.md [Unreleased]`。
- **org 設定（不在 repo 內）**：org ruleset + `Policy Freshness` required workflow，需 `admin:org`，由使用者套用。
- **release**：feature 先進 `[Unreleased]`；`flat` profile 於 merge 當下才 batch bump。
