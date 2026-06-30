## 1. P0 — 核心 + R-22 refactor（Python parity）

- [ ] 1.1 (RED) 寫 `tests/test_doc_drift_symbols.py`：ctags 對 fixture 抽出 scoped identity `(lang,kind,scope,name)`，斷言 `Foo.close` 與 `Bar.close` 可區分——先紅
- [ ] 1.2 (RED) 寫 `tests/test_doc_drift_diff.py`：scoped-identity 差集——限定式→FAIL、裸名部分刪→WARN、裸名完全消失→FAIL——先紅
- [ ] 1.3 實作 `policy_check/doc_drift/langs.py`：語言註冊表 + Python kind 白名單
- [ ] 1.4 實作 `policy_check/doc_drift/symbols.py`：`git archive <sha>` → ctags → scoped identity 集合
- [ ] 1.5 實作 `policy_check/doc_drift/refs.py`、`paths.py`：自 `_doc_links.py` 抽共用面（link/code-span → path 候選 / symbol token；path 在 base/HEAD 存在性）
- [ ] 1.6 實作 `policy_check/doc_drift/drift.py`：scoped-identity 差集 + 限定式/裸名比對語義（FAIL/WARN/ambiguous）
- [ ] 1.7 實作 base/HEAD git 物件供給：取精確 SHA、`git cat-file -e` 驗證、缺則 fetch、仍缺 fail-fast（含單元測試）
- [ ] 1.8 refactor `r22_doc_reference.py`：symbol prong 改呼叫核心（語言無關 scoped）；path prong 改呼叫核心 primitive
- [ ] 1.9 1.1/1.2 轉綠；`python3 -m pytest -q tests/test_rule_r22_doc_reference.py` 既有測試全綠（parity）

## 2. P1 — R-24 refactor 上核心 + coverage primitive

- [ ] 2.1 (RED) 寫 `tests/test_doc_drift_coverage.py`：orphan + static freshness，含「自訂受治理前綴」案——先紅
- [ ] 2.2 實作 `policy_check/doc_drift/coverage.py`：orphan（產物未被 map 連結）+ static freshness；受治理前綴參數化（預設沿用現值）
- [ ] 2.3 refactor `r24_moc_alignment.py`：map 懸空改呼叫核心 path-drift、orphan/static 改呼叫 coverage；前綴由 config 取得（預設不變）
- [ ] 2.4 2.1 轉綠；`python3 -m pytest -q tests/test_rule_r24_moc_alignment.py` 既有測試全綠

## 3. P2 — Action + Python（doc-drift / moc 兩 mode）

- [ ] 3.1 (RED) 寫 `tests/test_doc_drift_cli.py`：薄 CLI 兩 mode 的 exit code（FAIL→非零、WARN→零）——先紅
- [ ] 3.2 實作薄 CLI 入口 `policy_check/doc_drift/__main__.py`：吃 base/head SHA + mode + 前綴 input，輸出清單與 exit code，零 `.paul-project.yml` 依賴
- [ ] 3.3 Action 自 GitHub event 取 PR base/head 精確 SHA，委由核心供給契約（淺層 checkout 下不前置 fatal）
- [ ] 3.4 建 `.github/actions/doc-drift/action.yml`（composite）+ ctags 安裝步驟 + `run.sh`
- [ ] 3.5 建 `examples/doc-drift/` demo fixtures：一個通過案、一個 known-bad 失敗案
- [ ] 3.6 在 `.github/workflows/self-test.yml` 加 doc-drift self-test job：demo green/red 斷言 + **shallow-checkout（`fetch-depth: 1`）情境**斷言不前置 fatal
- [ ] 3.7 寫 `.github/actions/doc-drift/README.md`：定位、輸入/輸出、base 供給契約、lychee 互補、已知侷限、多語言支援表
- [ ] 3.8 3.1 轉綠；本機跑 CLI 對 demo 驗證 green/red

## 4. P3 — bash 語言支援

- [ ] 4.1 (RED) 寫 bash fixture + 測試：刪 bash function → 限定式引用 FAIL——先紅
- [ ] 4.2 `langs.py` 註冊 bash（ctags Sh kind 白名單）+ 驗證 scope 欄位粒度並記錄
- [ ] 4.3 4.1 轉綠；Action README 多語言表加 bash

## 5. P4 — C/C++ 語言支援

- [ ] 5.1 (RED) 寫 C/C++ fixture + 測試：刪 C/C++ symbol → 限定式引用 FAIL——先紅
- [ ] 5.2 `langs.py` 註冊 C/C++（ctags C/C++ kind 白名單）+ 驗證 scope 欄位粒度並記錄
- [ ] 5.3 5.1 轉綠；Action README 多語言表加 C/C++

## 6. P5 — 誤報雙軌 UX

- [ ] 6.1 (RED) 寫測試：inline marker 豁免單一引用、`.doc-drift-allow` 批次豁免——先紅
- [ ] 6.2 核心實作 inline marker 解析（語法定稿）+ `.doc-drift-allow` glob/symbol 讀取，統一套用於 refs/paths/symbols
- [ ] 6.3 R-22/R-24/Action 同享豁免；6.1 轉綠

## 7. 收尾（docs / changelog / policy gate）

- [ ] 7.1 R-18：同步主 `README.md`（R-22/R-24 描述、Action 總覽、lychee 互補）
- [ ] 7.2 連結本案產物進 `docs/MOC.md`（避免 R-24 orphan WARN）
- [ ] 7.3 每 phase 補 `changelog.d/25-<slug>.md`；`CHANGELOG.md [Unreleased]` 收錄
- [ ] 7.4 `python3 -m pytest -q` 全綠
- [ ] 7.5 `python3 -m policy_check --repo .` 無 failure
- [ ] 7.6 `.github/pull_request_template.md` checklist 全勾；PR body `Closes #25`（zh-tw）
