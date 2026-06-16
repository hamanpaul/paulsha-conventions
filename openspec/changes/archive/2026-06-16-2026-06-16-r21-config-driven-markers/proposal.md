## Why

R-21（機密掃描）目前把雇主標記**寫死**在 `r21_secret_scan.py` 的 `_EMPLOYER_MARKERS` regex（`brcm|broadcom|airoha|prplos|prplog|bgw720|build20` 加 `/home/` 路徑）。兩個問題：

1. **調整 marker 要改 code、發版**——無法依 repo 或情境彈性增刪。
2. **把公開技術名一律當機密**：`brcm`/`broadcom`/`airoha`/`prplos`/`marvell` 等是公開廠商／開源 OS 名，對「合法支援這些平台的開源工具」（如 `serialwrap`，一個開源序列 console 工具）造成大量誤殺，使其無法在 `tier: shareable` 下通過 R-21。

需要把 marker 清單從 code 外部化為**設定資料**，並區分「真正 employer/個人 specific」與「公開技術名」。

## What Changes

- R-21 偵測拆為兩層：
  - **結構偵測器**（留 code、always-on、免設定）：個人絕對路徑 `/home/<user>/`、`-----BEGIN PRIVATE KEY-----`。
  - **Marker tokens**（config-driven）：字面 token 清單，從 code 移到資料。
- 新增**引擎 baseline 資料檔** `policy_check/data/secret_scan_defaults.yml`：`markers`（預設 `bgw720`、`build20`）與 `public_names`（預設 `brcm`/`broadcom`/`airoha`/`mtk`/`mediatek`/`prplos`/`prplog`/`marvell`）。
- `.paul-project.yml` 的 `secret_scan` 擴充 `markers` 與 `public_names`（皆 optional `list[str]`，**extend-only** 疊加到 baseline）；既有 `allow`（檔案路徑豁免）不變。R-08 schema 驗證新欄位。
- 減敏 = 改設定：中央改 baseline 資料檔（發版傳播），或單 repo 在 `.paul-project.yml` 增補（免發版）。本次將 vendor/OS 名從 baseline markers 移除、列入 baseline `public_names` 作決策記錄。
- 行為僅在 `tier: shareable` 強制（不變）；除「vendor 名不再 flag」外行為等價。

## Capabilities

### Modified Capabilities
- `secret-scan`：機密標記由 config 驅動（baseline 資料檔 + per-repo extend），並明確區分 confidential markers 與 public names。

## Impact

- 改 `policy_check/rules/r21_secret_scan.py`、`r08_policy_config_schema.py`；新增 `policy_check/data/secret_scan_defaults.yml`；更新 R-21 tests/fixtures。
- `policy_version` 1.0.3 → **1.0.4**；下游 caller 經既有流程 repin 傳播。
- 向後相容：既有 `secret_scan.allow` 不變；新 key 選配；無 `secret_scan` 區塊的 repo 套 baseline。
- 後續（不在本 change）：doc-alignment governance 見 issue #11；R-21 v2 結構偵測器（案號/email/hostname）與 LLM 輔助複審層。
