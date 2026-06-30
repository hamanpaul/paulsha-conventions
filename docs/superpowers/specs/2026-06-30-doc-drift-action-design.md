# doc-drift 獨立 Action（OSS-ready）設計（#25 子項 1）

> 日期：2026-06-30 ｜ 對應 issue：#25（子項 1：doc-drift 抽成獨立 Action）｜ 分支：`feature/25-doc-drift-action`
>
> 範疇定案：完整 OSS-ready；允許拆多 spec / 多 phase，但**一次規劃到底**（propose + writing-plans 全做完）、**逐 spec 驗收、全部落在同一個 PR**。語言優先序 Python（主）→ bash（次）→ C/C++（再次）。R-24（MOC alignment）**納入**本單元。

## 背景與問題

paulsha-conventions 的對外差異化，評估後集中在 **deterministic doc–code drift**（R-22 + R-24，業界幾無對手）。若要 OSS，最小可分享單元是把這層抽成**零設定、diff-aware、語言無關**的獨立 GitHub Action，可被外部 repo `uses:`。

現況的症結（要解的兩件事）：

1. **symbol 抽取寫死 Python**：`r22_doc_reference.py` 的 `_DEFCLASS_RE` 只認 `def`/`class`、`_removed_symbols()` 只 `git diff -- *.py`。這正是 issue 點名「語言無關 symbol 抽取是成敗點」、且要避開 DOCER regex 侷限之處。
2. **沒有可獨立 `uses:` 的零設定單元**：現有 `.github/actions/policy-check/` 是 composite，直接跑整包 `policy_check`，依賴 `.paul-project.yml`／`.project-policy.yml`、profile/version 驗證等政策機制，無法當通用工具對外曝露。

## 定位與邊界

- **是什麼**：偵測「docs/散文引用了**本次變更刪掉的 code symbol 或 in-repo 路徑／受治理產物**」的 deterministic 檢查器。對外敘事聚焦 **symbol-drift**（業界真空白）。
- **不是什麼**：不檢外部 URL 活性、HTTP、anchor——那是 **lychee** 的領域。README 明示「外部連結請搭 lychee」，**不重造**。我們只做 offline、git-level、deterministic 的 in-repo 引用存在性。
- **零設定**：不要求 `.paul-project.yml`／policy 機制；輸入來自 GitHub event（PR base ref）＋少量 action input ＋ git。

## 設計原則

1. **單一真相，不 drift**：doc-drift 核心邏輯只有一份，`policy_check` 的 R-22／R-24 與對外 Action **共用同一套**。自家 repo 與對外工具跑同一邏輯，是 OSS 的說服力來源；也避免「自家引擎與發佈工具行為分歧」。
2. **核心按 primitive 組織，不按 rule**：rule（R-22／R-24）與 Action mode 都是薄 consumer，組合 primitive 而成。
3. **deterministic 優先**：抽取引擎用 **universal-ctags**（已驗 PATH 上有 6.2.0），語言無關、原生支援 Python/Bash/C/C++（~40 語言），輸出 `{name, kind, lang}`；不走 regex-per-language（DOCER 失敗模式）。
4. **最小必要變更**：R-22／R-24 行為語義維持等價（既有測試續綠），只是把實作換成共用核心並語言無關化。

## 架構：共用核心 + 多 consumer

```
policy_check/doc_drift/                共用、語言無關的核心（按 primitive 組織）
  refs.py        從 docs 抽引用：markdown link + code-span → path 候選 / symbol token
  paths.py       path 在 base/HEAD 的存在性 → removed（本次刪）/ dangling（陳年）
  symbols.py     ctags(base) vs ctags(HEAD) 的 symbol 集合差集 → removed_symbols
  coverage.py    orphan（受治理產物未被 map 連結）+ static freshness
  langs.py       ctags lang → 哪些 kind 算 public symbol（語言註冊表）
       │
       ├── policy_check R-22  = refs + paths + symbols
       ├── policy_check R-24  = refs + paths(scoped to governed prefixes) + coverage
       └── standalone Action
              ├─ doc-drift mode      = refs + paths + symbols（OSS 賣點）
              └─ moc-alignment mode  = refs + paths + coverage（治理前綴可設定）
```

> 既有事實佐證此切法天然：`r22_doc_reference.py` 與 `r24_moc_alignment.py` **目前已共用** `_doc_links.py`（`LINK_RE`／`path_candidates`／`git_tracked`／`resolve_base`）。本設計把這份共用面正式抽成 `doc_drift/` 核心並語言無關化。

## symbol-drift 演算法（取代 Python-only regex）

1. 對 `base` 與 `HEAD` 兩個 git ref，各以 `git archive <ref>` 拉到 temp 目錄後跑 ctags（deterministic、不污染 worktree）。
2. 依 `langs.py` 的 kind 白名單，把 ctags 輸出收斂成 symbol **名稱集合**。
3. `removed = base_symbols − head_symbols`。
4. docs 的 code-span token 命中 `removed` → **FAIL**（本次刪除）；指向不存在但非本次刪的 → **WARN**（陳年，advisory）。

語義與現行 R-22 一致（本次刪 FAIL／陳年 WARN），差別只在語言無關。

**已知侷限（誠實寫進 README）**：ctags 以**裸名**比對，同名 symbol 不分 scope（兩個 class 同名 method 會被視為同一名）——與現行 R-22 同等，列為 tuning 點（靠 kind 白名單收斂，必要時未來再加 scope 限定）。

## path-drift 與 lychee 邊界

- 共用核心**保留** path-drift（R-22／R-24 都需要）：in-repo 路徑／檔案／受治理產物引用是否還在 git tree（offline、deterministic）。
- 外部 URL／anchor／HTTP 活性 → **不做**，文件導引使用者搭配 lychee。兩者互補、無重疊。
- Action 的 doc-drift mode 同時曝露 path + symbol（完整 in-repo drift），但**行銷敘事講 symbol**。

## R-24（MOC alignment）整合

R-24 三塊各自歸位到核心 primitive：

| R-24 子檢查 | 行為 | 歸到核心 |
|---|---|---|
| **map dangling** | `moc.map` 連到已刪的受治理產物 → FAIL（本次）／WARN（陳年） | `paths`（path-drift 變體） |
| **orphan** | plans/specs/active openspec change 未被 map 連結 → WARN | `coverage` |
| **static freshness** | `moc.triggers` 命中但 `moc.static` 未同步 → WARN | `coverage` |

**OSS-generic 化的主要工**：現行 R-24 把治理前綴**寫死**（`openspec/changes/`、`docs/superpowers/plans|specs/`）。要對外曝露 moc-alignment mode，需把這些前綴**參數化成 config／action input**（預設沿用現值，policy 內行為不變）。

## 誤報治理 / allowlist UX（zero-config，雙軌）

issue 點名的成敗點之一。採**雙軌**，實作於核心 → R-22／R-24／Action 同享：

1. **inline marker（主）**：doc 內以 HTML 註解標記豁免（例：行尾或前一行 `<!-- doc-drift-ignore -->`）。最 zero-config，適合「就是要提到一個已刪的東西」。
2. **optional allowlist 檔（次）**：`.doc-drift-allow`（每行一個 glob／symbol），批次豁免用；與現行 R-22 `doc_reference.allow` 同型，但對外工具不依賴 `.paul-project.yml`。

> marker 的確切語法（`ignore` vs `ignore-next`、是否帶 reason）於 P5 spec 定稿；本設計只定下「雙軌 + 實作於核心」。

## 封裝與「demo repo 跑綠」（單一 PR 約束下）

- Action 落 `.github/actions/doc-drift/`（沿用現有 `policy-check` action 慣例），對外 `uses: hamanpaul/paulsha-conventions/.github/actions/doc-drift@vX.Y.Z`。composite：安裝 universal-ctags（`apt-get` 或 setup step）＋跑薄 CLI。
- **薄 CLI 入口**：`python -m policy_check.doc_drift`（或獨立 console script），吃 GitHub event／git／action input，吐 doc-drift／moc 結果，零 `.paul-project.yml` 依賴。
- **「demo repo 跑綠」在單一 PR 約束下**落地為 **in-repo `examples/doc-drift/` 小 fixture + self-test CI job**：一個 green 案、一個 known-bad red 案，斷言行為。README 附 `uses:` 片段。獨立成另一個 GitHub repo 是日後品牌定案後的事（issue Non-goal）。
- **獨立 README**：`.github/actions/doc-drift/README.md`（定位、輸入、輸出、lychee 互補、已知侷限、多語言支援表）。

## Phase 拆解（多 spec、逐 spec 驗收、**同一 PR**）

一個 OpenSpec change 內含多個 spec delta，tasks 依 phase 切；全部落在 `feature/25-doc-drift-action` → 一個 PR。

| Phase | 內容 | 驗收標準 |
|---|---|---|
| **P0 核心 + R-22** | 建 `doc_drift/` primitives（refs/paths/symbols/langs，ctags base/HEAD 差集）；R-22 refactor 為呼叫核心 | R-22 既有測試全綠（Python parity）；核心有單元測試 |
| **P1 R-24 上核心** | R-24 refactor 上核心；新增 `coverage` primitive；治理前綴**參數化** | R-24 既有測試全綠；前綴可由 config 覆寫 |
| **P2 Action + Python** | `action.yml` + 薄 CLI + zero-config；doc-drift／moc 兩 mode；獨立 README；in-repo demo + self-test CI | 外部 `uses:` 跑得動；demo green/red 各一斷言通過 |
| **P3 bash** | `langs.py` 註冊 bash + fixtures | 刪 bash function 被抓為 FAIL；fixtures 綠 |
| **P4 C/C++** | `langs.py` 註冊 C/C++ + fixtures（抽象的真正考驗） | 刪 C/C++ symbol 被抓為 FAIL；fixtures 綠 |
| **P5 誤報 UX** | inline marker + `.doc-drift-allow`，實作於核心 | 兩種豁免皆生效；R-22／R-24／Action 同享；有測試 |

每 phase 走 TDD（先 RED）。語言能力＝「ctags 認得 + `langs.py` 註冊 kind 白名單」，故 P3／P4 近零核心改動，主要是註冊 + fixtures。

## 測試與 policy 合規

- 每 phase **TDD**：先寫失敗測試（ctags 差集、各語言 fixture、Action self-test 的 green/red），確認 RED 為**正確原因**後再實作。
- 全程在 `feature/25-doc-drift-action` worktree；每 phase 補 changelog fragment `changelog.d/25-<slug>.md`。
- R-18：README/docs 隨介面變動同步（Action README、多語言支援表、主 README 對 R-22/R-24 的描述）。
- 完成前：`python3 -m pytest -q` 全綠、`python3 -m policy_check --repo .` 無 failure、PR 走 zh-tw、checklist 全勾。
- PR body 以 `Closes #25` 收尾（R-17 closing-keyword）。

## Non-goals

- 不在本案決定授權條款 / 品牌定位 / 是否立即公開 OSS（issue Non-goal）。
- 不重造外部連結／HTTP 活性檢查（交給 lychee）。
- 不把 Action 拆成獨立 GitHub repo（單一 PR 約束；日後品牌定案再說）。
- 不改變 R-22／R-24 對外**語義**（FAIL/WARN 判準維持等價），只換實作為共用核心並語言無關化。

## 待 P-level spec 定稿的開放點

- inline marker 的確切語法與是否帶 reason（P5）。
- ctags kind 白名單逐語言內容（P0 Python、P3 bash、P4 C/C++ 各自定）。
- moc-alignment mode 的治理前綴 input 命名與預設（P1/P2）。
- Action 安裝 ctags 的方式（`apt-get` vs 既有 setup action vs container）（P2）。
