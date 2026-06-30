## Context

完整設計見 `docs/superpowers/specs/2026-06-30-doc-drift-action-design.md`（含 ASCII 架構圖、演算法步驟、phase 表）。本檔聚焦技術決策與取捨。

現況：doc↔code drift 邏輯（R-22 path+symbol、R-24 MOC map/orphan/static）綁在 `policy_check`，symbol 抽取寫死 Python（`_DEFCLASS_RE` + `git diff -- *.py`），且 `r22`/`r24` 已共用 `_doc_links.py`。要對外曝露為零設定、語言無關的 OSS Action，需把共用面正式抽成核心並語言無關化。範疇：完整 OSS-ready、多 phase、單一 PR；語言序 Python→bash→C/C++。

## Goals / Non-Goals

**Goals:**
- 單一真相核心 `doc_drift/`，R-22/R-24/Action 共用，永不 drift。
- 語言無關 symbol-drift（ctags），Python/bash/C/C++。
- 零設定、可外部 `uses:` 的 Action，自理 git 供給。
- 誤報雙軌豁免（inline marker + allowlist 檔）。

**Non-Goals:**
- 不重造外部 URL/HTTP/anchor 檢查（→ lychee）。
- 不拆獨立 GitHub repo（單一 PR）。
- 不決定授權/品牌。
- 不放寬 R-22/R-24 對外語義。

## Decisions

**D1：抽取引擎用 universal-ctags（非 tree-sitter/regex）。** ctags 單一成熟依賴、原生支援 ~40 語言、deterministic、出 `{name,kind,scope,line}`；加語言近零成本。tree-sitter 精度更高但每語言要接 grammar+query、依賴重；regex 即 DOCER 失敗模式（C/C++ 多行簽名/macro 不可靠）。本機已驗 ctags 6.2.0。

**D2：核心按 primitive 組織（refs/paths/symbols/coverage/langs），非按 rule。** R-22 = refs+paths+symbols；R-24 = refs+paths(scoped)+coverage；Action 兩 mode 各組合之。理由：rule 與 Action mode 都是薄 consumer，避免邏輯重複。佐證：`r22`/`r24` 現已共用 `_doc_links.py`。

**D3：共用核心 + refactor R-22/R-24（非 fork）。** 對外 OSS 工具與自家引擎跑同一套是說服力來源，且避免雙套長期 drift。代價：要改 R-22 行為與測試——可接受，因語義單調更嚴或等價。

**D4：Action 自理 base/head git 物件供給（adversarial review [high] #1）。** 標準 `actions/checkout@v4` 預設 `fetch-depth: 1`，PR base commit 常不在 checkout 內，`git archive <base>` 會在分析前 fatal。決策：Action 取**精確 SHA** → `git cat-file -e` 驗證 → 缺則自 `git fetch`（必要時 unshallow）→ 仍缺則 **fail-fast 印可行動訊息**。「zero-config」限指不需 policy 設定檔，git 供給由 Action 自理。替代（要使用者自設 `fetch-depth: 0`）被否決——破壞零設定承諾。

**D5：symbol-drift 用 scoped identity（adversarial review [high] #2）。** 收斂成 `(lang, kind, scope, name)` 而非裸名集合。限定式引用（`Foo.close`）精確比對→FAIL；裸名引用保守——完全消失才 FAIL、部分刪→WARN 標歧義。理由：裸名集合對常見方法名 fail-open（`Foo.close` 刪、`Bar.close` 留，`close` 仍在集合）。替代（維持裸名+列 tuning 點）被否決——headline 檢查不該靜默失效。

**D6：path-drift 留在核心、lychee 互補不重疊。** 我們只做 offline、git-level 的 in-repo 引用存在性；外部 URL/anchor/HTTP 交給 lychee，README 導引組合。

**D7：R-24 治理前綴參數化。** 現行寫死 `openspec/changes/`、`docs/superpowers/plans|specs/`；對外曝露需可由 config 覆寫，預設沿用現值（policy 內行為不變）。

## Risks / Trade-offs

- [ctags scope 欄位粒度依語言而異，C/C++ 可能不齊] → P0/P3/P4 各自驗證並記錄 kind/scope 白名單；fixtures 涵蓋每語言。
- [裸名指涉被刪的同名 symbol 無法判定意圖] → 只 WARN 不 FAIL（避免誤報），限定式引用不受限；誠實寫進 README 已知侷限。
- [CI 環境缺 ctags] → composite Action 安裝步驟負責；self-test 驗證。
- [R-22/R-24 refactor 改動行為致既有測試紅] → 語義設計為單調更嚴或等價，既有測試應續綠；紅燈即視為迴歸處理。
- [base SHA fetch 需 token 權限] → fail-fast 訊息指明；self-test 含 shallow-checkout 情境。

## Migration Plan

- 分 phase（P0 核心+R-22 → P1 R-24 → P2 Action+Python → P3 bash → P4 C/C++ → P5 誤報 UX），逐 phase TDD，全部落單一 PR。
- R-22/R-24 為**就地** refactor（同 capability），無資料遷移；rollback = 還原 commit。
- feature 先進 `[Unreleased]`；merge 當下依 flat profile batch bump。

## Open Questions

- inline marker 確切語法（`ignore` vs `ignore-next`、是否帶 reason）— P5 定稿。
- ctags kind/scope 白名單逐語言內容 — P0/P3/P4 各定。
- moc-alignment mode 治理前綴 input 命名與預設 — P1/P2。
- Action 安裝 ctags 方式（`apt-get` vs setup action vs container）— P2。
