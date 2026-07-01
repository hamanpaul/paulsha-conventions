# Rule Families + README 版號 generated-fact 自我強制 — 設計 spec

> 制定日期：2026-07-01 · profile: flat · 目標版本：1.0.11（PATCH）
> 分支：`feature/rule-families-version-fact`

## 1. 背景與動機

三件互相關聯、但各自獨立的改善，合為一個 feature batch：

1. **規則呈現太扁**：`policy_check` 報告把 26 條規則平鋪、依 `rule_id` 排序。先前的規則重量／合併可行性分析已確認「合併 rule_id」是錯的工具（`R-NN` 是三重錨定的對外契約：規則原始碼 `exempt_label` + CLAUDE.md 白名單 + README 規則總表 + 測試 `get_rule("R-NN")` + 下游釘選），正解是在**呈現層**用 family 分組——拿到「更少概念桶」的 UX，完全不動 `rule_id`／exemption label／inventory／測試。

2. **README 手抄事實已漂移（實測缺口）**：`main` 上 canonical 真相全一致（`VERSION`/`.paul-project.yml`/tag 皆 1.0.10），但 `README.md` 有兩處手抄自我描述陳舊：
   - 版號 `當前版本：…（現為 1.0.7）` — 自 1.0.8 起漂移三個 release。
   - 規則範圍 `本 repo 為 R-01~R-23 完整實作` — R-24/25/26 落地後未更新。
   根因：**沒有任何規則在驗證 README 裡自由書寫的版號**。R-14 只管 agent 檔、R-20 只管 workflow、R-02 只檢查 `## Version` *段落存在*不看值。而引擎自己**本來就有**能守這種漂移的規則——R-26 `generated_facts`——只是本 dogfood repo 一直沒對自己 opt-in。

3. **release 流程沒有版號訂正的守門**：README 版號能對，純靠發版 SOP（sed/手動）自律，非規則強制；散文式事實連 SOP 的 pattern 都掃不到。

## 2. Goals / Non-goals

**Goals**
- G1：報告依 family 分組呈現；family 分類集中在單一可審視處；新增規則若漏分類，測試會擋。
- G2：修正 README 兩處陳舊事實；版號改為 R-26 可強制的 generated-fact marker。
- G3：對本 repo 啟用 R-26（dogfood），使「README 版號 ↔ `VERSION`」漂移在**每個 PR** 被擋（不只 release）。

**Non-goals（明確排除）**
- N1：**不做 auto-fix / regenerate script**。R-26 FAIL 打槍 PR，由 agent／人手動更新 marker（使用者決策）。
- N2：**不把規則清單數／inventory 做成 fact**。規則數屬 CHANGELOG／RELEASES.md 版本譜系，不在 README 硬寫、不獨立成規則（使用者決策）。
- N3：不新增 CLI flag（分組為預設行為，`--help` 輸出不變 → R-16 cli-help marker 不受影響）。
- N4：不新增、不合併、不改號任何 `rule_id`；不改任何 exemption label。
- N5：不動 R-26 規則本體語義（只是本 repo opt-in）。

## 3. 詳細設計

### Part 1 — Family 分組（呈現層）

**新增 `policy_check/rules/families.py`：**
- 定義一份**有序**的中央分類：`FAMILIES: list[tuple[str, tuple[str, ...]]]`，每項為 `(family_name, (rule_id, ...))`，順序即報告輸出順序。
- 提供 `family_of(rule_id) -> str`（反查；未分類回 `"OTHER"`）與 `ordered_families() -> list[str]`。
- 提議分類（11 family）：

  | family | 成員 |
  |---|---|
  | `README` | R-01, R-02 |
  | `CHANGELOG` | R-03, R-04, R-09 |
  | `VERSION` | R-05, R-06, R-07 |
  | `CONFIG` | R-08 |
  | `PR` | R-10, R-11, R-12, R-17 |
  | `AGENT` | R-13, R-14 |
  | `WORKFLOW` | R-15, R-20, R-23 |
  | `MARKER-SYNC` | R-16, R-26 |
  | `CI` | R-19 |
  | `SECRET` | R-21 |
  | `DOC-ALIGN` | R-18, R-22, R-24, R-25 |

**`report.py` 變更（`emit`）：**
- 由「平鋪 sorted by rule_id」改為「依 `ordered_families()` 分組，family 標題（如 `### VERSION`）下列該 family 的規則，family 內按 `rule_id` 排序」。
- **保留不變**：頂部 summary 計數（pass/fail/warn/skip）、每條規則的 icon／message／exempt／detail 區塊、`return 1 if fails else 0` 的 exit code 契約。
- 介面：`emit(results, families: dict[str, str] | None = None)`；`families` 為 `rule_id -> family` 映射，`None`（未提供）時 fallback 回舊平鋪行為（向後相容，不破壞既有呼叫）。

**`cli.py` 變更：**
- `run` 內組出 `families = {r.rule_id: families_mod.family_of(r.rule_id) for r in rules}`，傳給 `emit(results, families)`。
- 註：`--only R-05,R-06` 篩選後只剩部分規則時，report 只顯示有結果的 family（空 family 不印）。

**完整性測試（新）：**
- 斷言 `registry.load_all()` 的每個 `rule_id` 都**剛好**屬於 `FAMILIES` 中一個 family（無漏、無重複）。防止新增規則忘記分類。
- 斷言 `FAMILIES` 內無未知 `rule_id`（防 typo / 已刪規則殘留）。

### Part 2 — README 訂正

**版號（原 L271）** 改為 generated-fact marker 區塊（HTML 註解在 rendered markdown 不可見，只顯示版號）：
```
當前版本（權威值見 `VERSION`）：

<!-- BEGIN: generated-fact marker="repo-version" -->
1.0.10
<!-- END: generated-fact marker="repo-version" -->
```
- marker 內容 = `cat VERSION` 的正規化 stdout（`normalize` = `.strip()`）。marker 區塊內只放版號字串，不含其他散文（否則 normalize 後不等於 `1.0.10`）。

**規則範圍（原 L269）** 移除手抄的「本 repo 為 R-01~R-23 完整實作」；改述為不綁數字（例：「累積已完成的 feature batch」），並指向 `RELEASES.md`／`CHANGELOG.md` 為規則清單權威。

### Part 3 — R-26 dogfood（零新程式碼）

**`.paul-project.yml` 新增：**
```yaml
generated_facts:
  - command: "cat VERSION"
    reflected_in: "README.md"
    marker: "repo-version"
```
- R-08 已驗 `generated_facts` 為 list[mapping]（無需改 R-08）。
- R-26 自此對本 repo 生效：每次 `policy_check`（含每個 PR）執行 `cat VERSION`、正規化、比對 README 的 `repo-version` marker 區塊；不一致／marker 缺失 → **FAIL**。這正是 §1.2 缺口的守門。

**release SOP 更新：**
- `RELEASES.md` 的升版 SOP 與 release-process 記憶：bump 清單加一條「更新 README `repo-version` marker（＝新 `VERSION`）」。R-26 為安全網（漏更新則 release PR 的 CI 會擋）。

## 4. 架構與邊界（isolation）

- `families.py`：純資料 + 兩個查詢函式，無副作用、無依賴 rule 實作，可獨立測試。
- `report.emit`：唯一改動點是「分組排列」；輸入（results + optional families map）明確，`families=None` 保舊行為 → consumer 不破壞。
- rule 本體、`RuleResult`、`RuleContext`、registry：**完全不動**（family 是外掛分類，不侵入 rule）。
- Part 2/3 為 config + 文件變更，無程式碼耦合。

## 5. 測試策略

1. `test_families.py`：完整性（每 rule_id 剛好一個 family）＋ `family_of` / `ordered_families` 行為。
2. `test_report_grouping.py`：給定假 results + families map，斷言輸出含 family 標題、family 順序正確、family 內按 rule_id、summary 與 exit code 不變；`families=None` 時等同舊平鋪。
3. R-26 dogfood：
   - green：README marker == `VERSION` → 本 repo `policy_check --repo .` 中 R-26 PASS（由 NA 轉 PASS）。
   - red：暫時改 `VERSION`（或 marker）使兩者不符 → R-26 FAIL（以 tmp fixture repo 或 monkeypatch 驗，不污染真檔）。
4. 全 suite 續綠；`policy_check --repo .`（含 PR context）無 fail。

## 6. Rollout / 版本

- 屬 feature batch（flat profile）→ merge 後 PATCH bump 1.0.10 → 1.0.11（另走既有 release 流程）。
- 本 PR：feature 落地 + 一個 changelog fragment（`changelog.d/<slug>.md`, type: feat / fix）。
- 語言：hamanpaul repo → PR/commit/comment 全 zh-tw。

## 7. 風險與緩解

- **R1**：README 加 R-26 marker 後，若「1.0.10」寫錯或 `cat VERSION` 尾端換行處理差異 → R-26 FAIL。緩解：`normalize=.strip()` 已容忍尾端換行；red-case 測試涵蓋。
- **R2**：report 分組改動若破壞既有依賴輸出格式的下游（如有人 grep `## R-` 樣式）。緩解：per-rule 區塊格式（`## icon R-NN — status`）保持不變，只是多了 family 標題；summary/exit code 不變。
- **R3**：family 分類主觀。緩解：集中單檔、測試守完整性；分類可後續無痛調整（純呈現、零 ID 成本）。
- **R4**：`generated_facts` 首次對本 repo 生效，可能連帶暴露其他未預期的 marker 檢查。緩解：只宣告一個 entry（version），scope 明確。

## 8. Self-review 檢核（實作前）

- 無 TBD／placeholder。
- Non-goals 明確排除 auto-fix、rule-count fact、CLI flag、ID 變動。
- Part 1（碼）與 Part 2/3（config/docs）邊界清楚、可分別驗收。
