## Why

`hamanpaul` 帳號把雇主機敏內容——Broadcom/MTK/prplOS build 路徑、`BGW720` 等裝置識別、內部案件編號——放在 public repo 裡。已在 `testpilot`、`logsensing`、`dts-build`、`IntelliDbgKit` 確認，另外 `serialwrap` 也 commit 了憑證樣式的 env 檔。policy 引擎目前沒有任何規則能偵測這些：R-19 加了「CI 跑測試」、R-20 管 workflow `policy_version` 同步，但沒有規則掃描機敏內容。repo 的可見性目前是建立時隨手決定，而不是內容分類的結果，所以機敏內容是因疏忽、而非決策進入 public repo。

本 change 讓可見性變成「依內容宣告、可被檢查」的屬性，並補上缺席的偵測防線。

## What Changes

- 新增 policy 規則 **R-21（機密掃描）**：掃描 tracked 文字檔，比對雇主標記 denylist、個人絕對路徑、憑證模式；當 repo 宣告的 tier 要求內容可公開、卻命中標記時 FAIL。
- 在 `.paul-project.yml` 加 `tier: shareable | work | personal` 欄位，由既有 schema 規則（R-08）驗證；R-21 讀取它決定嚴格度。
- 依內容 tier 重新分類並遷移帳號 repo：
  - `testpilot`、`logsensing`、`dts-build`、`IntelliDbgKit` → private（含雇主內容）。
  - `serialwrap` → 將 `brcm.env` / `OPI.env` 清成 `*.example` 後維持 public。
- 建立 canonical→下游 同步（「路 B」：private canonical + `paulc-arc` read collaborator + 純 `upstream` git remote，2026-06-14 已實證），並在下游 work repo 放 `SYNC.md`。
- archive 已被取代的 `openclaw-obsidian-deploy` 與 `custom-claw-tools`。

## Capabilities

### New Capabilities
- `secret-scan`：偵測「宣告 tier 要求內容可公開」之 repo 內的雇主機敏內容，並要求每個納管 repo 宣告內容 tier。

### Modified Capabilities
- 無。`.paul-project.yml` schema 新增 `tier` 欄位，屬 `secret-scan` 的實作細節。

## Impact

- 新增 policy 規則 R-21，`policy_version` 升版（1.0.2 → 1.0.3）；下游 caller 經既有流程同步新版本。
- repo 可見性變更：4 個 public→private、2 個 archive，並在脫鉤後刪除既有的 `paulc-arc/testpilot`、`paulc-arc/dts-build` public fork。
- `serialwrap` 移除已 commit 的 `*.env`，改為 `*.example`。
- 帳號遷移屬一次性操作，記在 `tasks.md`；只有 `secret-scan` 能力產生持久的 spec delta。
- 來源設計記錄（private Obsidian vault）：`~/notes/REPO-refine/docs/REPO-reorg-r1-visibility-sync.md`。
- 不在本輪範圍（延後）：`testpilot` core/plugin 切分、`serialwrap` package 化與測試鏈共用 schema、agent 基礎設施整併、版號制度決策、fan-out sync bot、規則瘦身。
