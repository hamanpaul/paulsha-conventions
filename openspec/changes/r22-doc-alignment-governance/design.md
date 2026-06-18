## Context

`policy_check` 是確定性 gate（同輸入→同 PASS/FAIL）。現有規則抓不到「文件內容陳舊」：
R-18 只看「PR 有沒有碰 docs」、不看內容。issue #11 要求補上。完整技術設計見
`docs/superpowers/specs/2026-06-18-r22-doc-alignment-governance-design.md`；本文聚焦決策與
取捨。

## Goals / Non-Goals

**Goals:**
- 確定性、可重現、可在 CI 擋 merge 的「結構性懸空引用」偵測。
- 抓得到 motivating 案例（docs 引用被搬出的 `def`/`class`）而不被陳年舊帳淹沒。
- 下游導入無痛（陳年 rot 不擋）。

**Non-Goals:**
- 裸 prose 的 symbol 偵測、語意陳舊判斷（屬 Tier 3 LLM/人，不可重現、不做硬 gate）。
- 跨語言 symbol（v1 僅 Python `def`/`class`）、markdown 錨點存在性。
- 把 PR/commit/spec 的 narrative 做成確定性觸發器。

## Decisions

- **三層治理，只有 Tier 2 可強制**：Tier 1（agent checklist 預防）與 Tier 3（Copilot
  語意複審）皆 advisory；Tier 2（R-22）是它們漏掉時的安全網。理由：語意判斷不可重現，
  不能當硬 gate。
- **只看結構化引用**：路徑、內部連結、反引號 token；不掃裸 prose。裸文字交 Tier 3。
  理由：把高 FP 的語意判斷推給 LLM 層，確定性層保持低 FP。
- **一個偵測器 + diff-aware 嚴重度**（取代「A 規則 vs B 規則」兩套）：B（這次弄壞的）⊆
  A（所有懸空），故只做一個偵測器、用 `base..head` diff 分級。理由：不養兩套引擎。
- **Per-category 策略**：路徑/連結走快照存在性（FP 近零）；symbol 走 **diff-driven only**
  （起點是「本次移除的 symbol」而非 doc token），不做全域 symbol 稽核。理由：全域
  symbol grep 的 FP/FN 過高，diff 起點天然只抓新破壞。
- **掃描排除** `openspec/**`、`docs/superpowers/**`、自身 fixtures：spec/plan 會故意引用
  未建產物。理由：避免引擎掃自己與規格文件誤報。
- **設定與 schema 同屬 doc-reference capability**：`doc_reference.allow` 與其 R-08 型別
  驗證是本 capability 的契約，故不改既有 capability 需求（無 MODIFIED）。
- **版本 1.1.0（MINOR）**：新增可強制規則＝行為變更，下游 pin 者需明確版本訊號。

## Risks / Trade-offs

- [symbol 偵測 FP] → diff-driven only + symbol-shape 啟發式（含 `_` 或混大小寫、長度門檻）。
- [陳年 rot 造成採用噪音/被狂掛豁免] → diff-aware：陳年僅 WARN、不擋；只有新破壞 FAIL。
- [本地 `--repo .` 無 diff、無法分級] → 優雅降級：Prong P 降 WARN、Prong S 關閉；仍可當 lint。
- [跨語言 symbol rot 漏接] → 由 Tier 3 Copilot 覆蓋；引擎日後以 config 擴充語言。
- [規格/spec 文件被誤掃] → 明確排除 `openspec/**`、`docs/superpowers/**` 與 fixtures。

## Migration Plan

- 實作先進 `CHANGELOG [Unreleased]`，`policy_version` 維持 1.0.4-dev；發版時統一 bump
  1.1.0（`VERSION`/`pyproject`/`.paul-project.yml`/四份 agent 檔/`managed-by@v1.1.0`）、補
  `RELEASES.md`、打 `v1.1.0` tag → R-07/R-14/R-20 保持綠。
- Rollback：規則隔離於 `r22_doc_reference.py`，移除檔案即停用；無資料遷移。
- 下游：pin 新 engine SHA + 設 `policy_version: 1.1.0`；陳年 rot 僅 WARN，首個 PR 不被擋。

## Open Questions

- 無（brainstorm 兩個 edge case 已定：全新 doc 引用從未存在路徑→WARN；symbol v1 僅 Python）。
