# 跨 repo policy 漂移治理設計（#23）

> 日期：2026-06-25 ｜ 對應 issue：#23 ｜ 分支：`feature/23-cross-repo-drift-governance`
>
> 修訂：2026-06-25 依 Codex adversarial review 修正 [high]（強制路徑）與 [medium]（`-fix.N` 排序）。

## 背景與問題

`policy_version` bump 時，下游 repo（`.github`、`new-project-template`、其他 `hamanpaul/*`）目前靠**手動 per-repo PR** 追上 canonical（最近 1.0.5 → 1.0.7 即如此）。R-14 / R-20 / R-23 只驗**單 repo 自洽**，看不到「某 repo 落後 canonical」這種**跨 repo 漂移**；一旦有人忘記同步，漂移會復發且 gate 不報。

## 設計原則：engine 強制，不主動改下游

paulsha-conventions 是**規則引擎 + canonical 來源**，職責是「定義規則 + 強制下游遵守」。據此定下硬邊界：

- **engine 不主動 mutate 下游 repo 的內容**（不 clone、不改檔、不替下游開升版 PR）。
- 落後的 repo 由**它自己的 agent** 依 SOP 升上來；engine 只負責「設門檻 + 擋不合格的 merge + 點名誰沒守」。

因此 #23 在 engine 這邊收斂成三件**不越線**的交付：

1. **org ruleset / required-workflow runbook**（強制層，由 org admin 手動套用）——其中 required workflow 跑 drift gate 對 live canonical 比對，**真正擋下落後 repo 的 merge**。
2. **drift 偵測器**（`policy_check/drift.py`，兩種模式：report 唯讀報表 / gate 落後即 fail）。
3. **升版傳播 SOP**（描述下游 repo 自助升版的步驟）。

明確**砍掉**原 issue candidate 裡「主動改下游檔的傳播 PR 機器人」。

### 為什麼強制不能是一條 R-xx 規則（核心推理）

「你是否落後 canonical」這個檢查**不能**做成 `python3 -m policy_check --repo .` 裡的 R-xx 規則。因為 R-xx 規則由**被釘住的引擎**執行——一個落後的 repo 釘的是落後的 engine，那份 engine 裡**沒有**新加的檢查。引擎無法強制「你已過期」，因為它本身就是過期的東西（bootstrapping 矛盾）。

所以跨 repo freshness 的強制必須住在**org 層集中控制、下游無法釘舊／無法靜默停用的 required workflow**：它引用 canonical 的**最新**版本（非各 repo 自釘版本），跑 drift gate，落後就 FAIL。這條 org workflow 與 per-repo 的 Policy Check（R-15/R-23 故意釘固定版以求可重現）**並存且職責不同**：

| 檢查 | 由誰控制 | 比對對象 | 答的問題 |
|---|---|---|---|
| per-repo Policy Check（R-14/R-20/R-23…） | 各 repo 自釘版本 | 該 repo 自身 | 此 repo 在**它釘的版本下**自洽嗎 |
| org freshness gate（本案新增） | org admin 集中、引用 canonical 最新 | repo 版本 vs **live canonical** | 你釘的版本**還是不是最新** |

## A. Drift 偵測器 — `policy_check/drift.py`

一支兩用工具：operator 手動跑的**報表模式**，以及 org required workflow 當 gate 跑的**檢查模式**。**不是 R-xx gate 規則**，不會出現在 `python3 -m policy_check --repo .` 的 FAIL 集合裡。

### 純邏輯（pytest 單測）

- `parse_policy_version(yaml_text: str) -> str | None`
  從 `.paul-project.yml` 內容抽出 `policy_version`；找不到回 `None`。
- `parse_version(ver: str) -> tuple[int, int, int, int]`
  解析 `MAJOR.MINOR.PATCH[-fix.N]` 為可比較 tuple `(major, minor, patch, fix)`；**無 `-fix` 尾註 → `fix = 0`**，故 `1.0.7`（fix 0）< `1.0.7-fix.1`（fix 1）< `1.0.7-fix.2`（fix 2）。格式不合則 raise。
- `classify(repo_ver: str | None, canonical_ver: str) -> str`
  回傳 `"current"` / `"behind"` / `"ahead"` / `"unmanaged"`：
  - `unmanaged`：`repo_ver is None`（repo 無 `.paul-project.yml` 或無 `policy_version`）。
  - 其餘以 `parse_version` tuple **完整比對**（含 `-fix.N`）：小於 → `behind`、等於 → `current`、大於 → `ahead`。
- `format_report(rows: list, canonical: str) -> str`
  渲染人類可讀表格（repo ｜ policy_version ｜ status）。`--json` 走另一條結構化輸出。

> [medium] 修正：`-fix.N` 一律納入排序，不可摺疊；`1.0.7-fix.2` vs `1.0.7` 必須判為 drift，hotfix 級漂移正是本案要抓的。

### I/O 邊緣（gh CLI，不進單測）

- `local_policy_version(path=".") -> str | None`：讀指定 repo 工作目錄的 `.paul-project.yml`（gate 模式在下游 CI 用）。
- `canonical_version_live(org, repo) -> str`：取 canonical 的**最新** `vX.Y.Z` **tag**（用 tags API，非 GitHub Release——本 repo 只打 tag、無 Release 物件，`releases/latest` 會 404；單一真相來源，與 RELEASES.md tag-driven 一致）。gate 模式據此判斷下游是否落後。
- `list_managed_repos(org) -> list[str]`：`gh repo list <org>` 列舉，逐個探 `.paul-project.yml` 是否存在（report 模式用）。
- `fetch_policy_version(org, repo) -> str | None`：`gh api repos/<org>/<repo>/contents/.paul-project.yml` 取 raw → `parse_policy_version`。

### CLI — 兩種模式

**報表模式（operator 手動，唯讀）**
```
python3 -m policy_check.drift report [--org hamanpaul] [--json]
```
- 列舉 org 內各 managed repo，對 live canonical 分類，印表格。
- **永遠 exit 0**：它是儀表板，不是 gate。

**檢查模式（org required workflow 當 gate）**
```
python3 -m policy_check.drift check [--against <canonical_ver>]
```
- 讀**當前工作目錄**這個 repo 的 `policy_version`，對 live canonical（或 `--against` 指定值）比對。
- `behind` → **exit 非 0（擋 merge）**；`current` / `ahead` / `unmanaged` → exit 0。
- 由 org-level required workflow 在每個下游 repo 的 CI 內呼叫；因 workflow 集中控制、引用 canonical 最新，落後 repo 無法靠釘舊版規避。

- 權限：report 用 `gh repo list` + `gh api .../contents`（讀）；check 用 `gh api .../tags`（讀，取最高版本 tag）。`repo` / `read:org` 即可。

### 報表輸出範例（示意）

```
canonical: 1.0.7  (hamanpaul/paulsha-conventions, latest tag)

REPO                         POLICY_VERSION   STATUS
paulsha-conventions          1.0.7            current
.github                      1.0.5            behind
new-project-template         1.0.6            behind
some-other-repo              —                unmanaged
```

## B. org ruleset runbook — `docs/org-ruleset-runbook.md`

engine 只放**文件**；實際操作需 `admin:org`，由使用者執行。內容：

- **目的**：org 層 require Policy Check **與 freshness gate**，涵蓋既有 repo、下游無法靜默停用，補掉「bootstrap 只管開站期」的盲區。
- **前置**：`admin:org` 權限；`gh` 已登入 org admin 帳號。
- **Step 1 — 建 org ruleset**：對目標 repo（或全 org）require status check 通過才能 merge；require PR、禁直推 `main`。附 `gh api`（`PUT /orgs/{org}/rulesets`）payload 範例 + UI 路徑。required checks 含：
  - `Policy Check`（per-repo 自洽，既有）。
  - **`Policy Freshness`（本案新增的 org required workflow，跑 `policy_check.drift check`）**——這條才是真正擋下「落後但自洽」repo 的 gate。
- **Step 2 — org-level required workflow / default setup**：把 `policy-freshness.yml` 以 org required workflow / default setup 推給所有 repo（不靠各 repo 自行 `include`）。該 workflow checkout canonical **最新**版的 drift 工具並跑 `check` 模式；範例 workflow YAML 附於 runbook。
- **Step 3 — 驗證（下游落後實驗）**：在一個落後 repo 開 PR → `Policy Freshness` 跑 `drift check` → 判 `behind` → exit≠0 → required check 失敗 → **merge 被擋**。截圖 / `gh api` 佐證。
- **與既有機制並存**：org freshness gate 與 `reusable-policy-check.yml` 的 R-15 / R-23 dual-pin 並存、職責不同（見上「核心推理」表），不重複造。
- **Non-goals**：不改規則引擎邏輯；GitLab 發行另見 #20。

## C. 升版傳播 SOP — `README.md` + `RELEASES.md`

- `README.md`「Doc-alignment governance」段新增子段「跨 repo 升版傳播（機制層）」：串起 freshness gate（擋）→ drift report（點名）→ 下游自助升版（修）三者關係。
- `RELEASES.md`：把現有「升版傳播 PR 必須同時更新…」那句擴成明確 SOP 區塊。**下游 repo 自己的 agent** 依序：
  1. 查 `RELEASES.md` 取 canonical 版本 + engine SHA。
  2. 改 `.paul-project.yml` 的 `policy_version`。
  3. re-pin `policy-check.yml` 的 `policy_engine_ref`（新 SHA）+ 補 `# vX.Y.Z` 尾註（R-23）。
  4. canonical `CLAUDE.md` 有變則更新（其餘三份 agent 檔為 symlink，自動跟隨）。
  5. `python3 -m pytest -q` 與 `python3 -m policy_check --repo .` 全綠。
  6. 開 zh-tw PR，body 寫 `Closes #N`（若有對應 issue）。

freshness gate 擋住未升版的 merge；drift report 告訴你**哪些** repo 要升；本 SOP 告訴下游 agent **怎麼**升。

## D. 收尾雜項

- `tests/test_drift.py`：單測（**RED first**）
  - `parse_version` / `classify` 的 `-fix.N` **完整排序**（含「無尾註 < `-fix.1`」「`1.0.7-fix.2` vs `1.0.7` 判 behind/ahead」）。
  - **落後但自洽**情境：repo `1.0.5` vs canonical `1.0.7` → `classify` 回 `behind`，gate 模式 exit≠0。
  - `format_report` 表格輸出。
- `CHANGELOG.md [Unreleased]`：補本批 entry（drift 工具 report+check + runbook + SOP）。
- `docs/MOC.md`：把本案 openspec change + plan + `docs/org-ruleset-runbook.md` 連進 `moc.map`，避免 R-24 orphan WARN。
- **不 bump 版本**：feature 先進 `[Unreleased]`；`flat` profile 於 merge 當下才 batch bump。
- **本輪 local commit only**：不 push / 不開 PR，除非使用者明確要求。

## 元件邊界與測試性

| 元件 | 做什麼 | 怎麼用 | 依賴 |
|---|---|---|---|
| `drift.py` 純邏輯 | 解析/排序版本、分類漂移、渲染報表 | `import` 後直接呼叫，pytest 單測 | 無（純函式） |
| `drift.py` report 模式 | 列舉 org repo、抓遠端版本、印表 | CLI `drift report`，exit 0 | `gh`（讀） |
| `drift.py` check 模式 | 比當前 repo vs live canonical | CLI `drift check`，behind→exit≠0 | `gh`（讀） |
| `docs/org-ruleset-runbook.md` | 文件化 org 強制（含 freshness gate） | org admin 照著做 | `admin:org`（使用者，不在 repo 內） |
| README / RELEASES SOP | 文件化下游自助升版 | 下游 agent 照著做 | RELEASES 版本譜系表 |

純邏輯與 I/O 邊緣分離，讓比對/排序演算法可在無網路、無 `gh` 的環境下單測；`gh` 取資只在邊緣，整合層由手動執行 + Step 3 實驗佐證。

## 驗收對照（issue #23）

| #23 驗收標準 | 本設計對應 |
|---|---|
| org ruleset 對目標 repo 強制 Policy Check | runbook Step 1（`Policy Check` + `Policy Freshness` 兩條 required check） |
| 既有 repo gate 失敗無法 merge | **`Policy Freshness` workflow 跑 `drift check`，落後 repo exit≠0 → required check FAIL → 擋 merge**（解 Codex [high]） |
| 有「升版傳播」SOP 或 script | 升版傳播 SOP（C）＋ drift report 工具 |
| 一次「下游落後」實驗被擋下或被修正 | runbook Step 3：落後 repo 開 PR → freshness gate 擋下 |

> 註：org ruleset / required workflow 屬 org 設定、不在 repo 檔內，需 org admin 權限；engine 內可交付的是**文件 + drift 工具（report/check）+ 範例 workflow YAML**，實際強制由使用者以 admin 套用 org ruleset 啟用。
