## MODIFIED Requirements

### Requirement: diff 驅動偵測 docs 對本次移除 symbol 的引用
R-22 MUST 委由 `doc-drift-core` 以 universal-ctags 對 `base..head` 計算本次被移除的 symbol（語言無關，不再限於 Python `*.py` 的 `def`/`class`），並以 **scoped identity** `(lang, kind, scope, name)` 比對 in-scope doc 的反引號引用：

- **限定式引用**（如 `Foo.close`、`mod.func`）命中本次被移除的 scoped identity 時 MUST 回報 FAIL。
- **裸名引用**（如 `close`）MUST 保守處理——僅當該名稱在 head **完全消失**才 MUST 回報 FAIL；若該名稱在 head 仍有同名留存（部分移除）MUST 回報 WARN（ambiguous）且 MUST NOT 靜默放過。

R-22 MUST NOT 對 docs 引用的 symbol 做全域稽核（不得僅因某 symbol 在 repo 找不到、但非本次移除而回報）。語言支援以 `doc-drift-core` 語言註冊表為準，至少涵蓋 Python；bash 與 C/C++ 依本案 phase 漸次納入。對外語義相對前版為單調更嚴或等價。

#### Scenario: 限定式引用命中本次移除的 symbol
- **WHEN** 本次變更移除 `Foo.close` 而保留 `Bar.close`，一份 in-scope doc 在 head 仍以反引號引用 `Foo.close`
- **THEN** R-22 回報 FAIL

#### Scenario: 裸名引用且同名仍留存
- **WHEN** 本次變更移除 `Foo.close` 而保留 `Bar.close`，一份 in-scope doc 在 head 仍以反引號引用裸名 `close`
- **THEN** R-22 回報 WARN（ambiguous），不回報 FAIL

#### Scenario: 裸名引用且名稱完全消失
- **WHEN** 本次變更移除所有名為 `foo` 的 `def`/`class`，一份 in-scope doc 在 head 仍含反引號 `foo`
- **THEN** R-22 回報 FAIL

#### Scenario: symbol 仍存在則通過
- **WHEN** 一份 in-scope doc 引用的 symbol 其定義在 head 仍存在
- **THEN** R-22 不因該 symbol 回報

#### Scenario: 非 Python 語言的 symbol 被本次移除
- **WHEN** 本次變更移除某 bash function 或 C/C++ symbol（該語言已在註冊表），一份 in-scope doc 在 head 仍以反引號限定式引用之
- **THEN** R-22 回報 FAIL
