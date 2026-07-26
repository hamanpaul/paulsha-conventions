# Issue 39：內部發行管道決策計畫

**Issue:** `hamanpaul/paulsha-conventions#39`

**狀態:** `needs_human`

## 現況判定

- #20 已交付引擎端 wheel、vendored dependencies、離線安裝 smoke、GitLab MR provider 與 pip-mode attestation。
- `README.md` 與既有 GitLab internalization spec 明確把正式發行管道留作公司決策。
- 本 issue 的四個候選（Artifactory、內部 PyPI、GitLab Package Registry、vendored wheel）牽涉公司既有基礎設施、權限、稽核與維運責任；repo 內沒有足夠 authority 讓 agent 自行選定。
- 引擎本體沒有待修 code；在決策前派 builder 修改 `paulsha-conventions` 會製造無依據的實作。

## 決策輸入

決策人需提供下列事實：

1. 公司現有且允許使用的 package service。
2. GitLab runner 到該 service 的網路路徑與認證供應方式。
3. package retention、immutable version、撤版與稽核要求。
4. 是否允許 build pipeline 對內部 registry 上傳 wheel 與 dependency closure。
5. air-gapped runner 是否只能接收預先封裝的 vendored wheel bundle。

## 候選比較

| 選項 | 適用條件 | 主要優點 | 主要風險 |
| --- | --- | --- | --- |
| Artifactory | 公司已營運 Artifactory 且 runner 有 token | Python/通用 artifact、權限與 retention 集中 | 需平台團隊建立 repo、權限與 immutable policy |
| 內部 PyPI | 已有受管 Python index | 最貼近 `pip install policy-check==X.Y.Z` | 需自行補齊稽核、鏡像、HA 與憑證輪替 |
| GitLab Package Registry | 專案與 runner 已在同一 GitLab authority | CI_JOB_TOKEN 整合直接、權限模型一致 | group/project scope、跨專案下載與保留策略需先定義 |
| vendored wheel bundle | runner 真正 air-gapped 或無 package service | 最少 runtime 依賴、現有 smoke 已證明 | 發布、同步、完整性、撤版與版本漂移需另建流程 |

## 決策後執行

1. 在公司 infra/config authority 所屬 repo 寫入正式來源、認證注入與 retention 設定。
2. 在一個非機敏 canary project 驗證：
   - 指定版本安裝；
   - dependency closure 完整；
   - runner 無外網時仍可安裝；
   - 不把 token 印進 log；
   - 版本不可靜默覆寫。
3. 更新下游 `.gitlab-ci.yml` 範本與 runbook；不得把公司 endpoint、token 或內部 project ID 寫入 shareable repo。
4. 若通用 engine 文件需要補充，只記錄 provider-neutral contract，不記錄公司內部值。
5. 以 canary log、package digest 與 rollback 演練作為 issue closure evidence。

## 驗收條件

- 決策人明確選定一個管道與 owner。
- canary 能執行 `pip install policy-check==X.Y.Z`，且安裝來源與 package digest 可稽核。
- air-gapped 約束、憑證輪替、retention 與 rollback 均有文件。
- shareable `paulsha-conventions` 不含公司 endpoint、帳號、token 或內部識別資訊。
- 在上述 authority 未提供前，Cortex 必須維持 `needs_human`，不得派實作 agent 猜測平台。
