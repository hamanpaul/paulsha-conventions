# 設計：Doc-Alignment 三層治理（含引擎規則 R-22 懸空引用偵測）

> 日期：2026-06-18
> 狀態：approved（使用者已逐段拍板）
> 對應 issue：#11（doc-alignment governance：偵測文件陳舊）
> 範圍：`paulsha-conventions`（policy 引擎 + 四份 agent 慣例檔 + README）
> 目標版本：`policy_version` 1.0.4 → **1.0.5**（PATCH，比照 R-17~R-21；merge 當下立即 bump）

## 1. 背景與目標

`serialwrap`、`testpilot`、`paulshaclaw` 等 repo 歷經多次架構調整（例：testpilot
`core ⊥ wifi_llapi` 解耦），不少文件仍殘留舊架構/過時資訊。現有規則抓不到這類
「文件陳舊」：R-01/R-02 只查 README 存在性與段落；R-16 只同步 CLI `--help` marker；
R-18 `docs_sync` 只看「PR 有沒有同時碰 docs」（advisory WARN、不看文件**內容**）。

issue #11 提議新增確定性規則（暫名 R-22）偵測「懸空引用」。本設計把它放進一個更完整
的三層治理框架——這是與使用者 brainstorm 後收斂的結果。

### 1.1 核心原則：確定性 gate 與語意判斷分工

與 R-21 同本質：**確定性規則抓得到「結構性陳舊」，語意陳舊要 LLM 或人。**
`policy_check` 每條 rule 都是可重現的確定性 gate（同輸入→同 PASS/FAIL），不「理解」
文字。判斷「PR/spec 在描述架構改變」「docs 描述是否過時」屬語意推理、不可重現，
不能當會擋 merge 的硬 gate（符合母辦法 AI-SEC-001 的 human-in-the-loop 原則）。

## 2. 三層治理架構

| 層 | 位置 | 執行者 | 性質 | 本設計落點 |
|---|---|---|---|---|
| **Tier 1 預防** | 本地 | agent（讀 convention 檔）| 勸導、不保證 | 四份 agent 檔 checklist |
| **Tier 2 確定性 gate** | GitHub CI | `policy_check` 引擎 **R-22** | 可重現、會擋 merge | 新增 rule + 測試 + R-08 schema |
| **Tier 3 語意複審** | GitHub PR | Copilot / LLM | 建議、不擋 | 四份 agent 檔 review 導引 + README |

三層互補：Tier 1 減少違規但 LLM 會忘 → 需 Tier 2；Tier 2 確定性但只看得到結構性
rot（引用死掉、產物被搬走）→ 抓不到「引用都在、描述卻過時」→ 需 Tier 3。
**只有 Tier 2 可強制執行**；Tier 1/3 是 best-effort——這正是 Tier 2 必須存在的理由：
本地 LLM 先更新是 happy path，R-22（CI）是它漏掉時的安全網。

### 2.1 為何 Tier 3 不讓 `copilot-instructions.md` 與其他三份分岔

本 repo 鐵律是四份 agent 檔內容完全同步（R-13/R-14）。doc-staleness 的 review 導引
對任何做 review 的 agent 都通用，因此**四份一起加**；Copilot 只是「剛好被接到 GitHub
PR review 的那一隻」（其 PR review 會讀 repo custom instructions，含
`.github/copilot-instructions.md`）。「把 Copilot 設為 reviewer」是 GitHub repo 設定、
非檔案，列為 README 建議、不強制、不在本 change 的可強制範圍內。

## 3. Tier 2 引擎規格：`policy_check/rules/r22_doc_reference.py`

- `rule_id = "R-22"`，`exempt_label = "policy-exempt:doc-reference"`。
- 一個懸空引用偵測器，**只看結構化引用**（反引號 token、markdown 連結、檔案路徑），
  **不掃裸 prose**（裸文字裡的 symbol 提及交給 Tier 3）。

### 3.1 掃描範圍與排除

- 範圍 = `README.md` + `docs/**`（對齊 R-18 對「docs」的定義）。
- **排除** `openspec/**` 與 `docs/superpowers/**`：spec/plan/brainstorm 產出會故意引用
  「還沒建的」產物（包括本設計自己會提到 `r22_doc_reference.py`），掃了只是噪音。
- **排除** rule 自身 fixtures `tests/fixtures/doc-reference/**`（self-exempt，避免引擎掃
  自己的測試資料誤報）。
- 額外尊重 `.paul-project.yml` 的 `doc_reference.allow`（見 §4）。

### 3.2 Prong P — 路徑 & 內部連結（doc-driven、快照）

對每份 in-scope doc：

- **markdown 內部連結** `[text](target)`：`target` 不符 `^(https?:|mailto:|#)` 者，去掉
  `#anchor` 後相對 doc 所在目錄解析為 repo 路徑，比對 head 的 git-tracked 檔案集合。
- **path-shaped token**（含於反引號或裸出現）：符合 `^[\w.\-/]+$`、含 `/`，且能解析到
  repo 根或符合已知 code 副檔名（`.py .sh .yml .yaml .toml .md .js .ts .json .cfg .ini`）
  者視為路徑候選，比對 git-tracked 檔案。
- 解析不到 → 懸空。錨點（`#anchor`）存在性 v1 不驗（見 §8）。

### 3.3 Prong S — symbol（diff-driven、不做全域稽核）

- 從 `base..head` diff 找**這次被刪/改名的 symbol 定義**：對 `code_paths` 涵蓋的檔案，
  symbol `foo` 視為「本次移除」若它在 **base** 有定義（`^\s*(def|class)\s+foo`）而 **head**
  無。此判定同時涵蓋「刪除」與「改名」（舊名在 head 消失）。v1 鎖 Python `def`/`class`。
- 對每個「本次移除」的 `foo`，掃 in-scope doc 在 head 是否仍有反引號 token 恰為 `foo`
  （且符合 symbol 形狀，見 §3.5）→ 命中。
- **起點是 diff、不是 doc token**，因此天生只抓「這次的新破壞」、零陳年噪音。陳年
  symbol rot 不在 Tier 2 抓（交給 Tier 3）。

### 3.4 嚴重度分級（diff-aware）

| 情境 | 嚴重度 |
|---|---|
| doc 路徑/連結目標被**這次 PR**刪掉（base 有、head 無）| **FAIL** |
| doc 路徑/連結為**陳年**懸空（base、head 都無）| **WARN** |
| doc 引用的 symbol 定義被**這次 PR**刪/改名（Prong S 命中）| **FAIL** |
| 無 diff context（本地 `--repo .`，無 `base_ref`）| Prong P 一律降 **WARN**；Prong S **關閉** |

WARN 不影響 exit code（`report.emit()` 為 `1 if fails else 0`），符合「不打斷 workflow」
偏好；FAIL 擋 merge。

### 3.5 偽陽性控制啟發式

- **symbol 形狀**（進 Prong S 的反引號 token）：符合 `^[A-Za-z_]\w*$`，且（含 `_` 的
  snake_case 或含內部大寫的 CamelCase），長度 ≥ 3——排除 `true`/`main`/`--help` 等。
- **路徑候選**（進 Prong P）：須含 `/` 或命中已知 code 副檔名，避免把 `${{ inputs.x }}`
  之類誤判為路徑。
- 最終 regex 細節於 plan/TDD 收斂，以測試固定行為。

### 3.6 可測性 seam 與優雅降級

- rule 把「給定 `repo_root` + `base_ref` → 回傳（本次移除的 symbols、base 的 tracked 檔案
  集合）」收斂成一個薄 seam（helper），測試以**真實 temp git repo**（base/head 兩個
  commit）驅動，比照 R-21 用真實 `git ls-files` 的作風。
- `base_ref` 缺失或無法解析（無 git/非 PR 脈絡）→ Prong S 跳過、Prong P 懸空降為 WARN
  （無法證明「本次移除」就不 FAIL）。本地 `policy_check --repo .` 即此降級路徑。

## 4. Config / 豁免 / R-08 schema

- **豁免 label**：`policy-exempt:doc-reference`（整條 rule skip，比照其他 rule → SKIP）。
- **`.paul-project.yml` `doc_reference.allow`**：doc-path glob 清單，比整 PR label 更細的
  逃生閥（給「故意引用已移除/歷史產物」的 doc）。比照 R-21 `secret_scan.allow`。範例：
  ```yaml
  doc_reference:
    allow:
      - "docs/legacy/**"
  ```
- **R-08 schema 擴充**（`r08_policy_config_schema.py`）：`doc_reference` 存在時，其 `allow`
  若存在須為 `list[str]`，型別不符 FAIL，比照 R-21 `secret_scan` 的 schema 檢查。

## 5. Tier 1 / Tier 3 內容（四份 agent 檔同步）

四份：`CLAUDE.md` / `AGENTS.md` / `GEMINI.md` / `.github/copilot-instructions.md`。

### 5.1 Tier 1 — checklist（預防）

- 「改 code 時」新增：`R-22：搬移/改名/刪除 code 產物（檔案、def/class）時，同步更新
  README.md / docs/** 中引用它的段落；無法即時處理上 policy-exempt:doc-reference 並附理由`。
- 「claim done 前」新增：`R-22：docs 對本次刪改產物的引用無懸空，或上
  policy-exempt:doc-reference`。
- Exemption Labels 白名單新增：`policy-exempt:doc-reference — R-22 文件懸空引用`。

### 5.2 Tier 3 — review 導引（新增一小段，四份都加）

> `## Doc-alignment review（PR review 時）`：review 變更時，除了 R-22 抓得到的懸空引用，
> 另留意**語意陳舊**——引用都還在、但 docs 描述了已被這次變更改掉的架構/行為；發現時於
> PR 留言指出、建議作者更新。Advisory，不擋 merge。

### 5.3 README

- 規則總覽表新增 R-22 列（含豁免 label）。
- 豁免 label 清單新增 `policy-exempt:doc-reference`。
- 新增「Doc-alignment governance（三層）」段，說明 Tier 1/2/3 分工，並註明「建議將
  GitHub Copilot 設為 PR reviewer 以啟用 Tier 3」。

## 6. 測試策略（TDD）

`tests/test_rule_r22_doc_reference.py`，fixtures 用真實 temp git repo（base/head commit），
涵蓋：

- clean repo → PASS。
- 路徑/連結目標**這次 PR 刪掉** → FAIL；**陳年**懸空 → WARN。
- doc 引用的 `def`/`class` **這次 diff 移除** → FAIL；symbol 仍在 → PASS。
- 豁免 label → SKIP；`doc_reference.allow` glob 命中該 doc → 不報。
- **無 `base_ref`** → 路徑降 WARN、symbol prong 關閉。
- `openspec/**`、`docs/superpowers/**`、自身 fixtures → 不掃。
- R-08：`doc_reference.allow` 非 list → FAIL（`tests/test_rule_r08_*` 或既有 R-08 測試擴充）。

CI 已有 R-19 保證 pytest 執行（`self-test.yml`），新測試自動納入 PR gate。

## 7. 版本與 rollout

- 版本級別 **1.0.5（PATCH）**：比照 R-17~R-21（每條新規則皆 PATCH bump）；flat profile 的
  PATCH = 「一個 feature batch 完成」，R-22 正是一個 batch。
- **本實作 PR 不 bump**（R-22 先進 `[Unreleased]`）：避免 `VERSION` 偏離最新 tag `v1.0.4`
  使 R-07 變紅、得掛 `release:*` label。
- **merge 當下立即** 執行 release bump：`VERSION`、`pyproject.toml`、`.paul-project.yml`、
  四份 agent 檔 `policy_version` 與 `managed-by@v1.0.5` 標記、打 `v1.0.5` tag、補
  `RELEASES.md` 一列 → R-07 / R-14 / R-20 同步保持綠。
- **新增 convention**：「PR 若 defer 版本 bump，merge 當下必須立即補做（不得留置）」寫進
  四份 agent 檔的「改版號時／claim done 前」段——補上 1.0.4 bump 半套的洞。
- **下游導入無痛**：陳年 rot → WARN 不擋，只有新破壞 FAIL，故 serialwrap / testpilot /
  paulshaclaw 第一個 PR 不會被舊帳紅；按自己步調 pin 新 engine SHA + 設
  `policy_version: 1.0.5` 即可。

## 8. Non-goals / 未來（明確排除，避免 scope 蔓延）

- **裸 prose 的 symbol 偵測**、**語意陳舊判斷**：屬 Tier 3（LLM/人），非 Tier 2 確定性
  範圍。
- **跨語言 symbol 定義偵測**：v1 僅 Python `def`/`class`；其他語言（C、shell 函式等）
  之 Prong S 留待後續，以 config 化模式擴充。
- **markdown 錨點（`#anchor`）存在性**：v1 僅驗檔案存在，不驗 heading 錨點。
- **narrative（PR/commit/spec）語意觸發**：屬 Tier 3，不做成確定性 trigger。

## 9. Artifact 清單（本 change 會動到的檔案）

**Tier 2（引擎）**
- `policy_check/rules/r22_doc_reference.py`（新增）
- `tests/test_rule_r22_doc_reference.py`（新增）
- `tests/fixtures/doc-reference/**`（新增 fixtures）
- `policy_check/rules/r08_policy_config_schema.py`（擴充 + 測試）
- `.paul-project.yml`（新增 `doc_reference.allow`，自身 dogfood）

**Tier 1 + Tier 3（四份 agent 檔同步）**
- `CLAUDE.md` / `AGENTS.md` / `GEMINI.md` / `.github/copilot-instructions.md`

**文件 / 版本**
- `README.md`（規則表 + 豁免清單 + 三層治理段）
- `CHANGELOG.md`（`[Unreleased]` entry）
- `VERSION` / `pyproject.toml` / `.paul-project.yml` / 四份 agent 檔 `policy_version`
  （merge 當下 bump 1.0.5）
- `RELEASES.md`（merge 後補 1.0.5 列）
