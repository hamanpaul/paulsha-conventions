# 設計：R-21 機密標記 config 化（policy 1.0.4）

## 背景與問題

R-21 把雇主標記寫死在 `_EMPLOYER_MARKERS` regex。後果：(1) 調 marker 要改 code 發版；(2) 公開技術名（broadcom/prplos/brcm/airoha/marvell…）被一律當機密，誤殺像 `serialwrap` 這種合法支援這些平台的開源工具。

## 目標

- marker 清單外部化為設定，**減敏＝改 config**。
- 區分「真正 employer/個人 specific」（產品型號如 `BGW720`、內部 build 標記、個人路徑、憑證）vs「公開技術名」。
- 僅 `tier: shareable` 強制（不變）；向後相容。

## 架構（兩層）

1. **結構偵測器（always-on，留 code，免設定）**：`/home/<user>/` 路徑、`-----BEGIN PRIVATE KEY-----`。結構明確、普世機密，不外部化也不可被 repo 關閉。
2. **Marker tokens（config-driven）**：字面 token（大小寫不敏感、word-boundary，引擎自動組 regex）。

## Config 來源與合併（extend-only）

- **引擎 baseline 資料檔** `policy_check/data/secret_scan_defaults.yml`（隨引擎發布、pin 傳播）：
  - `markers: [bgw720, build20]`
  - `public_names: [brcm, broadcom, airoha, mtk, mediatek, prplos, prplog, marvell]`
- **per-repo `.paul-project.yml` 的 `secret_scan:`**（皆選配）：
  - `markers: [...]`：疊加到 baseline（**extend-only**——不能移除 baseline marker；要壓掉某個就加進 `public_names`）。
  - `public_names: [...]`：疊加。
  - `allow: [...]`：既有檔案路徑豁免，**不變**。

選 extend-only 的理由：避免某 repo 把自己的 secret-scan baseline 設成空、削弱防護。需局部壓制時走 `public_names`（語意是「此 repo 認定該 token 為公開」），有意圖記錄。

## 判定流程（`tier: shareable` 時）

對每個 tracked 文字檔的每一行：
1. 檔案路徑命中 effective `allow`（baseline 無 allow；repo `allow` + 規則自身 `_SELF_EXEMPT`）→ 整檔跳過。
2. 命中結構偵測器 → flag。
3. 含 effective `markers`（baseline ∪ repo）中的 token，**且**該 token 不在 effective `public_names`（baseline ∪ repo）→ flag。
4. 其餘 → 不 flag。

`tier ≠ shareable`（含未設）→ 不 FAIL（WARN/skip，行為不變）。

## 減敏工作流

- **中央**：把 token 從 `secret_scan_defaults.yml` 的 `markers` 移除、或加進 `public_names`（記錄判定為公開）→ 發 conventions 版、下游 repin。
- **單 repo**：在該 repo `.paul-project.yml` `secret_scan.public_names` 增補 → 免發 conventions 版。
- 本次：`brcm/broadcom/airoha/mtk/mediatek/prplos/prplog/marvell` 從 baseline markers 移除、列入 baseline `public_names`。`bgw720`/`build20` 留在 markers。

## Schema（R-08）

project-config schema 的 `secret_scan` 物件：`allow`（既有）、`markers`、`public_names` 皆 optional `list[str]`；元素須為 str。非法 → R-08 FAIL。

## 向後相容

- 既有 `secret_scan.allow` 不變；新 key 選配；無 `secret_scan` 區塊 → 套 baseline。
- 行為等價：原 regex 的 `bgw720|build20` + path + key 全保留（移進 baseline/結構層）。唯一差異＝vendor 名不再 flag（本次刻意減敏）。

## 測試 / fixtures

- 既有 fixtures（`shareable-leak`/`shareable-allowlisted` 夾帶 `brcm broadcom BGW720`）→ 清為僅 `BGW720` 觸發；vendor 名不再觸發。
- 新增測試：baseline 自資料檔載入；per-repo `markers` extend；`public_names` 抑制 marker 命中；extend-only（repo 無法移除 baseline marker）；vendor 名（broadcom 等）在 shareable 不再 FAIL；結構偵測器 always-on（markers 為空時 path/key 仍 flag）。

## 釋出

- VERSION 1.0.3 → 1.0.4；CHANGELOG `[Unreleased]`；conventions 自身 4 份 agent 檔 + `.paul-project.yml` 版本標記同步 1.0.4；`python3 -m policy_check --repo .`（自掃）+ `pytest` 綠；打 `v1.0.4` tag。

## 不在本 change（延後）

- doc-alignment governance（懸空引用偵測等）→ issue #11，獨立 change。
- R-21 v2：結構偵測器（內部案號/email/hostname）、LLM 輔助複審層（WARN/建議、非 deterministic gate）。
