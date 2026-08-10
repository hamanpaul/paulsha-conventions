# arc-conventions portability — design

- Issue: [#63](https://github.com/hamanpaul/paulsha-conventions/issues/63)
- 狀態：設計待審
- 範圍：階段一（去硬編碼 + 信任模型重構）；階段二（rule plugin 介面）僅列介面草案

## 背景

要把本引擎導入 ARC 公司環境（內網 GitLab `vcs-sw2.arcadyan.com.tw`，無外網），對外發行身分暫定 `arc-conventions`。第一個目標 repo 是 `mcu/ti/ot-ti-mirror`。

已驗證的現況：

- 地端執行不需網路。`python3 -m policy_check --repo <path>` 對本 repo 可完整跑完並產出報告；`policy-preflight` 與 `policy-runtime-bundle` 皆有 `--offline`。
- 對 `ot-ti-mirror` 執行停在 `configuration error: Missing .project-policy.yml`，即**規則層只差一份 per-repo 設定**。
- GitLab 已是一等公民，不需重做：`rules/base.py:40` 的 `provider`、`pr_context.py:71` 的 `gitlab_pr_meta()`、`pr_context.py:98` 的 GitLab 優先分派、`r12_branch_source.py:26` 的 gitlab 分支。

擋住落地的不是規則層，而是**發行身分與信任鏈被寫死在原始碼常數**。

## 目標

1. 同一份 codebase 能以不同**發行身分**部署（`paulsha-conventions` / `arc-conventions`），不需 fork。
2. 信任模型在可設定化之後**不得被下游 repo 放寬**。
3. 既有 `hamanpaul/*` repo 行為完全不變（設定省略時等同現值）。
4. 全流程可離線完成，不假設 github.com 可達。

## 非目標

- rule plugin 機制（階段二，僅在本文件末尾列介面草案）
- 在 ARC GitLab 實際建立 repo（尚無權限）
- `ot-ti-mirror` 要啟用哪些規則的取捨（另行評估）

## 現況：信任模型如何運作

| 位置 | 現況 |
| --- | --- |
| `drift.py:17` | `CANONICAL_ORG = "hamanpaul"` |
| `preflight.py:39` | `CANONICAL_ENGINE_REPO = "hamanpaul/paulsha-conventions"` |
| `preflight.py:451-453` | `_is_canonical_checkout()` 只認 github.com 的三種 URL 形式 |
| `preflight.py:~470` | `_source_engine()`：`conventions_engine.repo` 若與常數不符 → `PreflightGateError` |
| `preflight.py:657-673` | 組 `https://github.com/{engine_repo}.git` → `git fetch --depth 1 origin <sha>` → 驗 `rev-parse HEAD == sha` |
| `runtime_bundle/verification.py:17` | `CANONICAL_REPOSITORY` 同樣寫死 |
| `runtime_bundle/builder.py:140-142` | 同樣寫死 github.com URL |
| R-15 / R-20 | 假設 workflow 位於 `.github/workflows/` |

關鍵性質（必須保留）：**`.project-policy.yml` 只能「聲明同意」，不能「改指向」**。`_source_engine()` 的 `PreflightGateError` 就是這條性質的實作 — 下游 repo 無法把自己的 authority 指到別處。

若把常數直接換成設定值讀取，這條性質會消失：攻擊者只要改一行 `.project-policy.yml` 就能把 engine 指向自己控制的 repo。**這是本設計的核心約束，不是單純的參數化工作。**

## 設計：三層身分

把「誰是 canonical authority」從**原始碼常數**下移為**發行單位（distribution）的身分**，並維持設定層只能 assert 不能 redirect。

```
第 1 層  distribution identity   由「建置／安裝這份引擎的人」決定，執行期唯讀
第 2 層  repo config             .project-policy.yml，只能宣告與第 1 層一致，不一致即 gate error
第 3 層  integrity               SHA pin + manifest digest（維持現行機制，不變）
```

### 第 1 層 — distribution identity

新增一個模組級的身分來源（暫名 `policy_check/identity.py`），解析順序：

1. 套件內建的 `policy_check/data/distribution.yml`（打包時寫入；預設值即現行 `hamanpaul` / `paulsha-conventions` / `https://github.com`）
2. runtime bundle 安裝時由 `install.sh` 寫入的同名檔（覆寫 1）

**不從環境變數、不從 repo 檔案讀取。** 身分屬於「這份被安裝的引擎」，不屬於「被檢查的 repo」，因此被檢查方無法影響它。

欄位：

```yaml
canonical_org: hamanpaul
engine_repo: hamanpaul/paulsha-conventions
remote_base: https://github.com        # engine fetch 的 base URL
distribution_name: paulsha-conventions # runtime bundle artifact 命名
provider: github                       # github | gitlab，決定 workflow 路徑等 provider 相依行為
```

ARC 發行版即：同一份 codebase，打包時帶入 `arc-conventions` 的 `distribution.yml`。

### 第 2 層 — repo config 的角色不變

`conventions_engine.repo` 的語意仍是「本 repo 聲明它受哪個 engine 管轄」。比對對象從常數改為第 1 層的 `engine_repo`；不一致仍拋 `PreflightGateError`。**放寬與否的權力留在發行方，未下放到被檢查的 repo。**

### 第 3 層 — integrity 不變

SHA pin、`rev-parse HEAD == sha` 驗證、manifest payload + sha256 全部保留。只有組 URL 的 base 改為讀第 1 層的 `remote_base`。

## 變更點

| 檔案 | 變更 |
| --- | --- |
| `policy_check/identity.py`（新增） | 載入與驗證 distribution identity；提供 `identity()` 單一入口 |
| `policy_check/data/distribution.yml`（新增） | 內建預設身分（值＝現行常數，確保零行為變更） |
| `drift.py:17` | `CANONICAL_ORG` → `identity().canonical_org` |
| `preflight.py:39` | `CANONICAL_ENGINE_REPO` → `identity().engine_repo` |
| `preflight.py:451-453` | canonical remote 集合由 `remote_base` + `engine_repo` 組出，涵蓋 https / ssh 兩種形式 |
| `preflight.py:657` | fetch URL 改用 `remote_base` |
| `runtime_bundle/verification.py:17`、`builder.py:140-142` | 同上，並以 `distribution_name` 命名 artifact 目錄 |
| `install.sh`（runtime bundle） | 安裝時寫入 distribution identity |

`provider` 欄位在階段一**僅保留於 identity schema 並固定為 `github`**，R-15 / R-20 的行為不變。GitLab 分支留到實際切換時處理（見「發行路徑」）。

## 錯誤處理

失敗一律 **fail-closed**，且訊息要能指出是哪一層不一致：

- `distribution.yml` 缺漏或欄位不全 → `PreflightGateError: distribution identity incomplete: <欄位>`；不得回退到硬編碼預設值（回退等同悄悄放寬信任）
- repo 宣告的 `conventions_engine.repo` 與 distribution identity 不符 → 維持現行 `PreflightGateError`，訊息同時列出雙方值
- `remote_base` 不可達（內網離線）→ 沿用 `--offline` 路徑：已安裝版本與 `policy_version` 相符即通過，否則 `offline artifact missing: repo=… sha=… version=…`（`preflight.py:807-811` 現行行為）
- `provider` 值非 `github` / `gitlab` → 設定載入期即報錯，不進入規則執行

## 測試策略

1. **零行為變更迴歸**：不放 `distribution.yml` 覆寫時，既有測試全綠（這是「既有 repo 零影響」的驗收依據）。
2. **替身分測試**：以 fixture 注入 `arc-conventions` 身分，驗證 canonical remote 集合、fetch URL、bundle 命名、R-15/R-20 路徑全部跟著切換。
3. **信任邊界測試（必要）**：`.project-policy.yml` 嘗試把 `conventions_engine.repo` 指向第三方 → 必須 `PreflightGateError`。此案例是本設計的核心不變式，需有獨立測試。
4. **離線測試**：`remote_base` 指向不可達位址 + `--offline` → 走已安裝版本比對路徑，不得嘗試網路。
5. **swap 演練**：以 fixture 將 `engine_repo` / `remote_base` 由 upstream 切到私有 fork，驗證 canonical remote 集合與 fetch URL 跟著改變 — 這是「日後切到 ARC GitLab 只需換設定」這項承諾的驗收依據。

## 相容性與遷移

- 內建 `distribution.yml` 的值等於現行常數 → 既有 `hamanpaul/*` repo 不需任何改動。
- `conventions_engine.repo` 語意未變，既有設定不需遷移。
- 唯一對既有使用者可見的變化：錯誤訊息會多列 distribution identity 來源。

## 階段二：rule plugin 介面（草案，不在本次交付）

現況 `rules/registry.py` 的 `load_all()` 只掃 `policy_check.rules` 套件目錄下 `rNN_*` 模組，且該套件有 `__init__.py`（非 namespace package），外部套件無法註冊規則；全 repo 無任何 entry point 機制。

介面草案與待決問題：

- 以 setuptools entry point group（例如 `policy_check.rules`）載入外部 `Rule` 子類
- 規則 ID 命名空間：外掛規則需前綴（例如 `ARC-01`），避免與 `R-NN` 衝突
- 執行順序、`--only` 過濾、report 呈現對外掛規則的處理
- R-08 設定 schema 需能容納外掛規則的設定區塊
- runtime bundle 從「單一整包」拆為「引擎 wheel + plugin wheel」對 builder / verification 的影響

## 發行路徑（已決策）

ARC 發行版**不直接落在 ARC GitLab**，分兩步走：

1. **現階段**：在 `hamanpaul` 名下開一支 **private GitHub fork** 作為 ARC 發行版的家。`remote_base` 仍是 `https://github.com`，只有 `engine_repo` 與 `distribution_name` 改變。引擎以**地端執行為主**（`policy-check` / `policy-preflight --offline`），不依賴 CI。
2. **日後**：真的需要時，再從該 fork 進 ARC GitLab，屆時只 swap `remote_base` 與 `engine_repo`。

此決策對階段一的影響：

- `remote_base` 仍必須可設定化（否則第 2 步做不到），但**不需在階段一驗證 GitLab 路徑**。
- `provider` 固定 `github`，R-15 / R-20 行為不變；GitLab 的 pinning 等價語意（`include:` vs `uses: xxx@sha`）留待切換時定義。
- 簽章**不做**。發行來源為私有 GitHub repo，安裝來源的可信度由該 repo 的存取權限提供。若日後進 ARC GitLab 或對外散佈，再評估 bundle 簽章。

## 待決事項

1. **版號策略**：upstream 引擎版號與 ARC 發行版號的關係尚未定案（見審查討論）。影響 R-07（`VERSION` 與 git tag 同步）與 R-23（pip mode 比對已安裝 `policy-check` 版本與 `policy_version`）。在定案前，實作不得觸及版號相關規則。
