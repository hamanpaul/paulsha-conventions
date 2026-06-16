# 設計

## 背景

`hamanpaul` 是 canonical/upstream 帳號；`paulc-arc`（工作帳號）消費它的 repo。雇主機敏內容會洩漏進 public canonical，原因有二：
1. 可見性是建 repo 時決定，而非由內容推導。
2. 沒有規則偵測機敏標記，洩漏在被人工發現前都是隱形的。

本設計同時修這兩點：可見性變成宣告的 tier，並由掃描規則強制執行。

## 決策 1 — 三級內容分類

每個納管 repo 在 `.paul-project.yml` 宣告 `tier`：

| tier | 可見性 | 同步 | 判準 |
|------|-------|------|------|
| `shareable` | public | — | 通用、無雇主內容 |
| `work` | private canonical | 路 B | 含 brcm/broadcom/MTK/airoha/prplOS/BGW720、內部路徑、案件編號 |
| `personal` | private | — | 私人專案 |

原則：canonical（hamanpaul）保持通用；工作客製只往下游 fork/overlay 流，永不回推 public canonical。

## 決策 2 — 路 B 同步（canonical private，下游以純 remote 同步）

private canonical 不靠 GitHub fork 也能讓 `paulc-arc` 消費：把 `paulc-arc` 加為 **read collaborator**，下游端再用純 `upstream` git remote。

**2026-06-14 已實證**（對 private 的 `hamanpaul.github.io`）：邀請被接受後，`paulc-arc` 的 `permissions.pull = true`，HTTPS clone 成功；事後已還原（移除 collaborator）。

選純 remote 而非 GitHub private fork 的理由：GitHub private fork 與 upstream 共用 network、權限相連、upstream 刪除會連動、可見性被綁住。單人擁有兩帳號時，fork 功能只帶來這些限制而無好處；純 `upstream` remote 讓下游完全獨立。

## 決策 3 — public→private 會讓既有 fork 脫鉤（遷移陷阱）

當 `hamanpaul/<repo>` 由 public 轉 private，GitHub **不會**把既有的 `paulc-arc/<repo>` public fork 一起私有化，而是把它脫鉤成獨立 public repo，並保留（可能含機敏的）內容。因此每次遷移都必須刪除脫鉤的 fork。受影響者為 `testpilot` 與 `dts-build`（兩者都有 `paulc-arc` public fork）。

## 決策 4 — R-21 機密掃描規則

- 檔案：`policy_check/rules/r21_secret_scan.py`（+ `tests/test_rule_r21_secret_scan.py` + fixtures）。R-20 已被佔用（workflow policy_version），故新規則編 R-21。
- 掃描 tracked 文字檔，比對可設定 denylist：
  - **雇主標記**：`brcm|broadcom|airoha|mtk|prplos|prplog|BGW720|build20` 加上案件編號樣式。
  - **個人絕對路徑**：`/home/<user>/`。
  - **憑證模式**：非 `*.example` 的 `*.env` 內 `KEY=<非空值>`、private key 標頭、token 樣式字串。
- **tier 感知嚴格度**：`tier: shareable`（public）命中為 **FAIL**；`work`/`personal` 降為 WARN 或 skip。
- **自我參照豁免**（正確性關鍵）：denylist 字串本身會出現在 `r21_secret_scan.py`、其 fixtures、以及合法引用這些標記的設計文件裡。規則必須排除自身規則檔、fixture 目錄、與指定的文件豁免清單，否則會掃到自己。
- 豁免沿用既有「白名單 label + 逐規則對應」機制。
- 互補（非本規則的一部分）：CI 另掛 gitleaks step 抓通用 secret；R-21 專責 gitleaks 不認得的雇主專屬標記。

## 遷移 pattern

- **P1 — shareable canonical + work overlay 下游**（`serialwrap`）：canonical 留 public 並清成 `*.example`；真值 env 只活在 `paulc-arc` 下游，以路 B 同步。
- **P2 — work canonical 轉 private**（`testpilot`、`logsensing`、`dts-build`、`IntelliDbgKit`）：canonical → private（雇主內容留內）；`paulc-arc` 取得 read collaborator；脫鉤的 public fork 刪除；視需要在下游重建 private 的路 B 副本。

## 已評估的替代方案

- **測試鏈收成 monorepo** — 否決：monorepo 只能單一可見性，但測試鏈跨 tier（`serialwrap` shareable vs `testpilot` work），且會破壞逐 repo 的路 B 同步粒度。
- **用 GitHub private fork 取代路 B** — 因上述 network/權限/刪除連動而否決。
- **全部維持 public、只靠掃描** — 否決：只靠掃描，每次手滑 commit 都留有真實殘餘洩漏風險；private canonical 直接移除 `work` 內容的曝險面，讓 R-21 成為第二道網而非唯一網。

## 不在本輪範圍（延後）

`testpilot` core/plugin 切分（執行期動態載入 private plugin、不抽 brcm）、`serialwrap` package 化 + 測試鏈共用 schema、agent 基礎設施所有權地圖、版號制度決策、fan-out sync bot、規則瘦身。
