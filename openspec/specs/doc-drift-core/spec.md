# doc-drift-core Specification

## Purpose
TBD - created by archiving change doc-drift-action. Update Purpose after archive.
## Requirements
### Requirement: 語言無關 symbol 抽取（universal-ctags）
doc-drift 核心 MUST 以 universal-ctags 對指定 git ref 抽取 symbol，收斂成帶 scope 的身分 `(lang, kind, scope, name)`，而非裸名集合。核心 MUST 維護**語言註冊表**決定每語言哪些 ctags `kind` 計為 public symbol；註冊表 MUST 至少支援 Python，並以同一機制可擴充 bash 與 C/C++（新增語言 MUST 不需改動差集演算法）。抽取 MUST 為 deterministic 且不污染 worktree（以 `git archive <ref>` 取該 ref 內容後掃描）。

#### Scenario: 抽取帶 scope 的 symbol 身分
- **WHEN** 對某 git ref 跑核心抽取，原始碼含 `class Foo` 內的 method `close`
- **THEN** 核心產出含 scope 的身分（區分 `Foo.close` 與其他 scope 的同名 symbol），而非僅裸名 `close`

#### Scenario: 新增語言不改差集演算法
- **WHEN** 在語言註冊表登記一個新語言與其 public `kind` 白名單
- **THEN** 該語言的 symbol 即納入抽取，差集與比對邏輯不需變更

### Requirement: scoped-identity symbol-drift 差集
核心 MUST 以 `removed = base_identities − head_identities` 計算本次移除的 symbol，並對 doc 的反引號 token 比對：限定式引用（如 `Foo.close`）MUST 精確比對 scoped identity，命中 `removed` 即判 FAIL；裸名引用（如 `close`）MUST 保守處理——僅當該名稱在 head **完全消失**才判 FAIL，若該名稱在 head 仍有同名留存（部分移除）MUST 判 WARN（ambiguous）且 MUST NOT 靜默放過。

#### Scenario: 限定式引用命中被刪 symbol
- **WHEN** 本次移除 `Foo.close` 而保留 `Bar.close`，某 in-scope doc 以反引號引用 `Foo.close`
- **THEN** 核心判 FAIL

#### Scenario: 裸名引用且同名仍留存
- **WHEN** 本次移除 `Foo.close` 而保留 `Bar.close`，某 in-scope doc 以反引號引用裸名 `close`
- **THEN** 核心判 WARN（ambiguous），不判 FAIL

#### Scenario: 裸名引用且名稱完全消失
- **WHEN** 本次移除所有名為 `legacy_init` 的 symbol，某 in-scope doc 以反引號引用 `legacy_init`
- **THEN** 核心判 FAIL

### Requirement: base/HEAD git 物件供給契約
核心 MUST 取得 base 與 head 的**精確 commit SHA**（非分支名），並在進行差集前驗證兩者的樹物件存在。當物件缺失（如 caller 採 shallow checkout）時，核心 MUST 嘗試 `git fetch` 取得；仍無法取得時 MUST fail-fast 並輸出可行動訊息，MUST NOT 靜默判 PASS。

#### Scenario: shallow checkout 缺 base 物件時自取
- **WHEN** 執行環境僅有 shallow checkout、base commit 物件不在本地
- **THEN** 核心先嘗試 fetch 取得 base 物件後再分析

#### Scenario: 無法取得 base 物件
- **WHEN** base 物件缺失且 fetch 後仍取不到
- **THEN** 核心 fail-fast 並輸出指明需擴大 fetch 深度或補權限的訊息，不判 PASS

### Requirement: 共用 path 與 coverage primitive
核心 MUST 提供 in-repo path-drift 與 coverage（孤兒/靜態鮮度）primitive，供 R-22、R-24 與 Action 共用，確保三者行為單一真相、不分歧。coverage 的受治理範圍 MUST 可參數化（預設沿用既有治理前綴）。

#### Scenario: R-22 與 R-24 共用同一 path-drift 判定
- **WHEN** R-22 與 R-24 各自呼叫核心的 path-drift primitive 判定某 in-repo 路徑引用是否懸空
- **THEN** 兩者對同一輸入得到一致結果

### Requirement: 誤報雙軌豁免
核心 MUST 支援兩種誤報豁免：(1) doc 內 **inline marker** HTML 註解，使被標記處的引用不判懸空；(2) optional **allowlist 檔**（每行一個 glob/symbol）批次豁免。兩者 MUST 由核心統一處理，使 R-22、R-24 與 Action 同享。

#### Scenario: inline marker 豁免單一引用
- **WHEN** 某 doc 引用一個已刪 symbol，但該處帶 inline ignore marker
- **THEN** 核心不對該引用判懸空

#### Scenario: allowlist 檔批次豁免
- **WHEN** 某引用命中 allowlist 檔的 glob/symbol
- **THEN** 核心不對該引用判懸空

