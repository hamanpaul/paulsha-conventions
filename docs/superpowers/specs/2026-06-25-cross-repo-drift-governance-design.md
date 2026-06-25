# 跨 repo policy 漂移治理設計（#23）

> 日期：2026-06-25 ｜ 對應 issue：#23 ｜ 分支：`feature/23-cross-repo-drift-governance`

## 背景與問題

`policy_version` bump 時，下游 repo（`.github`、`new-project-template`、其他 `hamanpaul/*`）目前靠**手動 per-repo PR** 追上 canonical（最近 1.0.5 → 1.0.7 即如此）。R-14 / R-20 / R-23 只驗**單 repo 自洽**，看不到「某 repo 落後 canonical」這種**跨 repo 漂移**；一旦有人忘記同步，漂移會復發且 gate 不報。

## 設計原則：engine 強制，不主動改下游

paulsha-conventions 是**規則引擎 + canonical 來源**，職責是「定義規則 + 強制下游遵守」。據此定下硬邊界：

- **engine 不主動 mutate 下游 repo 的內容**（不 clone、不改檔、不替下游開升版 PR）。
- 落後的 repo 由**它自己的 agent** 依 SOP 升上來；engine 只負責「設門檻 + 點名誰沒守」。

因此 #23 在 engine 這邊收斂成三件**不越線**的交付：

1. **org ruleset / required-workflow runbook**（強制層，由 org admin 手動套用）。
2. **read-only drift 偵測器**（只讀、只報，不改任何檔）。
3. **升版傳播 SOP**（描述下游 repo 自助升版的步驟）。

明確**砍掉**原 issue candidate 裡「主動改下游檔的傳播 PR 機器人」。

## A. Drift 偵測器 — `policy_check/drift.py`

唯讀的跨 repo 報表工具。**不是 R-xx gate 規則**，不會出現在 `python3 -m policy_check --repo .` 的 FAIL 集合裡；它是 operator 手動執行的 ops 工具。

### 純邏輯（pytest 單測）

- `parse_policy_version(yaml_text: str) -> str | None`
  從 `.paul-project.yml` 內容抽出 `policy_version`；找不到回 `None`。
- `classify(repo_ver: str | None, canonical_ver: str) -> str`
  回傳 `"current"` / `"behind"` / `"ahead"` / `"unmanaged"`。
  - `unmanaged`：`repo_ver is None`（repo 無 `.paul-project.yml` 或無 `policy_version`）。
  - 其餘以 semver（`MAJOR.MINOR.PATCH`，忽略 `-fix.N` 尾段比較主三段）比對 canonical。
- `format_report(rows: list, canonical: str) -> str`
  渲染人類可讀表格（repo ｜ policy_version ｜ status）。`--json` 走另一條結構化輸出。

### I/O 邊緣（gh CLI，不進單測）

- `canonical_version() -> str`：讀**本 repo** 的 `.paul-project.yml` `policy_version`（本 repo 即 canonical）。
- `list_managed_repos(org: str) -> list[str]`：`gh repo list <org>` 列舉，逐個探 `.paul-project.yml` 是否存在。
- `fetch_policy_version(org: str, repo: str) -> str | None`：`gh api repos/<org>/<repo>/contents/.paul-project.yml` 取 raw 內容 → `parse_policy_version`。

### CLI

```
python3 -m policy_check.drift [--org hamanpaul] [--json] [--help]
```

- 預設 `--org hamanpaul`。
- **永遠 exit 0**：它是報表，不是 gate（gate 是 org ruleset）。
- 權限：只用 `gh repo list` + `gh api .../contents`（讀），`repo` / `read:org` scope 即可。

### 輸出範例（示意）

```
canonical: 1.0.7  (hamanpaul/paulsha-conventions)

REPO                         POLICY_VERSION   STATUS
paulsha-conventions          1.0.7            current
.github                      1.0.5            behind
new-project-template         1.0.6            behind
some-other-repo              —                unmanaged
```

## B. org ruleset runbook — `docs/org-ruleset-runbook.md`

engine 只放**文件**；實際操作需 `admin:org`，由使用者執行。內容：

- **目的**：org 層 require Policy Check，涵蓋既有 repo、下游無法靜默停用，補掉「bootstrap 只管開站期」的盲區。
- **前置**：`admin:org` 權限；`gh` 已登入 org admin 帳號。
- **Step 1 — 建 org ruleset**：對目標 repo（或全 org）require「Policy Check」status check 通過才能 merge；require PR、禁直推 `main`。附 `gh api`（`PUT /orgs/{org}/rulesets`）payload 範例 + UI 路徑。
- **Step 2 — org-level required workflow / default setup**：評估把 `policy-check.yml` 推給所有 repo，不靠各 repo 自行 `include`。
- **Step 3 — 驗證（下游落後實驗）**：在一個落後 repo 開 PR，確認 gate 擋下 merge。
- **與既有機制並存**：org ruleset 與 `reusable-policy-check.yml` 的 R-15 / R-23 dual-pin 並存，不重複造。
- **Non-goals**：不改規則引擎邏輯；GitLab 發行另見 #20。

## C. 升版傳播 SOP — `README.md` + `RELEASES.md`

- `README.md`「Doc-alignment governance」段新增子段「跨 repo 升版傳播（機制層）」：串起 drift 偵測器 → org ruleset → 下游自助升版三者關係。
- `RELEASES.md`：把現有「升版傳播 PR 必須同時更新…」那句擴成明確 SOP 區塊。**下游 repo 自己的 agent** 依序：
  1. 查 `RELEASES.md` 取 canonical 版本 + engine SHA。
  2. 改 `.paul-project.yml` 的 `policy_version`。
  3. re-pin `policy-check.yml` 的 `policy_engine_ref`（新 SHA）+ 補 `# vX.Y.Z` 尾註（R-23）。
  4. canonical `CLAUDE.md` 有變則更新（其餘三份 agent 檔為 symlink，自動跟隨）。
  5. `python3 -m pytest -q` 與 `python3 -m policy_check --repo .` 全綠。
  6. 開 zh-tw PR，body 寫 `Closes #N`（若有對應 issue）。

drift 偵測器告訴你**哪些** repo 要升；本 SOP 告訴下游 agent **怎麼**升。

## D. 收尾雜項

- `tests/test_drift.py`：單測 `parse_policy_version` / `classify` / `format_report`（**RED first**）。
- `CHANGELOG.md [Unreleased]`：補本批 entry（drift 工具 + runbook + SOP）。
- `docs/MOC.md`：把本案 openspec change + plan + `docs/org-ruleset-runbook.md` 連進 `moc.map`，避免 R-24 orphan WARN。
- **不 bump 版本**：feature 先進 `[Unreleased]`；`flat` profile 於 merge 當下才 batch bump。
- **本輪 local commit only**：不 push / 不開 PR，除非使用者明確要求。

## 元件邊界與測試性

| 元件 | 做什麼 | 怎麼用 | 依賴 |
|---|---|---|---|
| `policy_check/drift.py` 純邏輯 | 解析版本字串、分類漂移、渲染報表 | `import` 後直接呼叫，pytest 單測 | 無（純函式） |
| `policy_check/drift.py` I/O 邊緣 | 列舉 repo、抓遠端 `.paul-project.yml` | CLI `python3 -m policy_check.drift` | `gh` CLI（讀） |
| `docs/org-ruleset-runbook.md` | 文件化 org 強制步驟 | org admin 照著做 | `admin:org`（使用者，不在 repo 內） |
| README / RELEASES SOP | 文件化下游自助升版 | 下游 agent 照著做 | RELEASES 版本譜系表 |

純邏輯與 I/O 邊緣分離，讓比對演算法可在無網路、無 `gh` 的環境下單測；`gh` 取資只在邊緣，整合層由手動執行佐證。

## 驗收對照（issue #23）

| #23 驗收標準 | 本設計對應 |
|---|---|
| org ruleset 對目標 repo 強制 Policy Check | `docs/org-ruleset-runbook.md` Step 1（使用者套用 + 截圖佐證） |
| 既有 repo gate 失敗無法 merge | runbook Step 1（require status check）+ Step 3 驗證 |
| 有「升版傳播」SOP 或 script | 升版傳播 SOP（C）— 採 SOP 形式（驗收標準允許「SOP 或 script」） |
| 一次「下游落後」實驗被擋下或被修正 | runbook Step 3 + drift 偵測器點名 |

> 註：org ruleset 屬 org 設定、不在 repo 檔內，需 org admin 權限；engine 內可交付的是**文件 + read-only 偵測器**，實際強制由使用者以 admin 執行。
