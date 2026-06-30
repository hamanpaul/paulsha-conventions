## Context

完整設計見 `docs/superpowers/specs/2026-06-30-doc-rule-hardening-design.md`。本文件只收斂
OpenSpec change 需要的關鍵技術決策與落地邊界。

目前文件規則有三個明顯缺口：

- `R-18` / `R-22` 只認 `README.md` 與 `docs/**`，看不到 repo 自己宣告的 canonical docs。
- 引擎無法 deterministic 地抓「新增了 X 卻沒記」的 omission drift。
- `R-16` 的 marker-sync 模式只服務 CLI help，無法重用在其他結構化事實。

這次變更同時碰到 config schema、既有規則行為、以及新的 deterministic gate，因此需要明確
切分 capability 與 rollout 順序，避免把所有邏輯塞進單一規則。

## Goals / Non-Goals

**Goals:**
- 為 documentation-related rules 建立共享的 canonical doc scope（`doc_paths`）。
- 在不破壞既有 repo 的前提下，新增 opt-in 的 deterministic omission gate。
- 把 marker-sync 模式一般化為可重用的 generated-fact protocol。
- 明確保留 semantic review 為 advisory 層，不污染 blocking deterministic gate。

**Non-Goals:**
- 不把純散文是否正確做成 blocking rule。
- 不要求所有 repo 在這一版立刻配置 `doc_coverage` 或 `generated_facts`。
- 不在第一版就移除 `R-16` 的既有 `cli` 設定入口。
- 不讓 engine 自動猜測 repo 的 RPC/CLI 結構；fact 抽取必須由明確 config 驅動。

## Decisions

### Decision 1 — 以 capability 分層，而不是把 `R-18` / `R-22` 擴成萬用規則
**選擇**：新增 `canonical-doc-scope`、`doc-coverage`、`generated-fact-sync` 三個 capability，
並只修改既有 `doc-reference` capability 的 scope 來源。

**理由**：`R-18`、`R-22`、`R-16` 目前各自回答不同問題；若把 scope、coverage、marker-sync、
semantic advisory 全塞進單一規則，會讓 config、測試與 rollout 全部糾纏。分 capability 後，
每層都有單一責任，也能獨立 opt-in。

**替代方案**：新增一個「萬用 doc-alignment rule」統包所有行為——否決，因為責任混雜、
相容性差、也不利於下游逐步採用。

### Decision 2 — `doc_paths` 為 top-level shared scope，`R-22` 保留內建排除
**選擇**：新增 top-level `doc_paths`（預設 `README.md` + `docs/**`），供 `R-18` / `R-22`
共用；`R-22` 仍保留 `openspec/**`、`docs/superpowers/**`、fixture tree 的內建排除。

**理由**：這補上 issue #26 最直接的盲區，同時避免把既有 spec/plan/fixture 噪音重新掃進來。
`doc_paths` 定義 canonical docs，內建排除則是 rule-level noise control，兩者責任不同。

**替代方案**：讓 `doc_paths` 完全覆蓋 `R-22` 的 effective scope——否決，因為會讓 default 行為
回歸並掃到原本刻意排除的樹。

### Decision 3 — coverage rule 採 opt-in，v1 預設 `mode: changed`
**選擇**：`doc_coverage` 未宣告時 rule 視為 not-applicable 直接 PASS；宣告後才啟用 gate。
v1 支援 `mode: changed` 與 `mode: all`，預設 `changed`。

**理由**：`changed` 模式最符合 issue #26 的「新增了 X 卻沒記」目標，也避免第一次導入時被
陳年未覆蓋事實打爆。`all` 模式保留給已經準備好做全量 coverage 的 repo。

**替代方案**：coverage 一律檢查所有 facts——否決，因為會把 feature rollout 變成一次性清舊帳工程。

### Decision 4 — built-in extractors 只接受明確、可測的 deterministic contract
**選擇**：v1 只支援四種 config-driven extractors：`modules`、`rpc_methods`、`env_vars`、
`cli_tree`，並固定它們的 fact identity 與抽取協議。

**理由**：這可避免不同實作者對「模組名怎麼算」「CLI 樹怎麼列」各自解讀，讓 coverage rule
維持穩定、可測、可預期。

**替代方案**：讓 rule 自由用 AST/regex/grep 猜 repo 的 public facts——否決，因為過度隱式且
跨 repo 不可預測。

### Decision 5 — generated-fact sync 一般化 protocol，但保留 `R-16` backward compatibility
**選擇**：新增 `generated_facts` 宣告與 generic marker protocol；同時保留既有 `cli-help`
marker 與 `R-16` 入口，先抽共用 helper，不在第一版強迫全部改寫。

**理由**：這能讓 repo 漸進採用通用機制，而不需要一次重做所有現有 CLI help 文件塊。

**替代方案**：直接讓 `R-16` 改吃新格式並移除舊格式——否決，因為 migration 成本不必要。

### Decision 6 — semantic correctness 留在 advisory 流程
**選擇**：純敘述是否正確的判斷不進 `policy_check` blocking rules；若未來實作，只能以 optional
workflow、nightly audit、或 reviewer guidance 形式存在。

**理由**：semantic 判斷不可重現，與 pinned-SHA deterministic gate 的契約相衝。

## Risks / Trade-offs

- [新 config 增加 repo 採用成本] → `doc_coverage` / `generated_facts` 採 opt-in，先讓 repo 可只吃 `doc_paths`。
- [`mode: changed` 需要 diff context] → base 無法解析時降為 WARN，不在缺乏證據時做 FAIL。
- [extractor contract 過度嚴格，repo 需要額外 helper script] → 允許用明確 command（如 `cli_tree`）產生 facts，但仍禁止 shell 與隱式猜測。
- [generic marker protocol 與舊 `R-16` 並存增加一段過渡期] → 以共用 helper 收斂底層行為，降低雙軌成本。

## Migration Plan

1. Phase 1：新增 `doc_paths`、補強 `R-18` / `R-22`、補 schema 與 regression tests。
2. Phase 2：新增 `doc_coverage` rule 與 built-in extractors，先落 `mode: changed`。
3. Phase 3：抽出 generic marker-sync helper，新增 `generated_facts` rule，保留 `R-16` 相容。
4. Phase 4：若需要 semantic audit，再以獨立 advisory 流程補上。

Rollback 採 capability 粒度：任何新 rule 或新 config surface 都可單獨回退，不需要資料遷移。

## Open Questions

- 無。brainstorm 與 adversarial review 已定稿的關鍵邊界為：`doc_coverage` 預設 opt-in、
  `mode: changed` 需 base context、`R-22` 保留內建排除、generic marker protocol 與 `R-16`
  並存。
