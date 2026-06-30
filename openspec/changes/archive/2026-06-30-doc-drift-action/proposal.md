## Why

paulsha-conventions 的對外差異化集中在 **deterministic doc–code drift**（R-22/R-24，業界幾無對手），但這層目前綁在 `policy_check`：symbol 抽取**寫死 Python**（`def`/`class`、`*.py`），且沒有可獨立 `uses:` 的零設定單元。要把它變成最小可分享的 OSS 工具，需抽出**語言無關、diff-aware、零設定**的核心與獨立 GitHub Action（issue #25 子項 1）。

## What Changes

- 新增**語言無關 doc-drift 核心** `policy_check/doc_drift/`，按 primitive 組織（refs/paths/symbols/coverage/langs），symbol 抽取改用 **universal-ctags**，支援 Python（主）→ bash → C/C++。
- symbol-drift 改 **scoped identity `(lang, kind, scope, name)`**：限定式引用精確比對、裸名保守（完全消失才 FAIL、部分刪→WARN 標歧義），消除同名 fail-open。**BREAKING（行為）**：R-22 由「Python 裸名」改為「語言無關 scoped」，語義單調更嚴或等價。
- 新增**獨立零設定 Action** `.github/actions/doc-drift/`，外部 repo 可 `uses:`；兩 mode：**doc-drift**（refs+paths+symbols）與 **moc-alignment**（refs+paths+coverage）。Action **自理 base/head SHA 供給+物件驗證+fail-fast**，不依賴 caller checkout 深度。
- 新增**誤報雙軌 UX**：inline marker（`<!-- doc-drift-ignore -->`）+ optional `.doc-drift-allow` 檔，實作於核心，R-22/R-24/Action 同享。
- **R-22 / R-24 refactor 上核心**（單一真相，不 drift）；R-24 治理前綴**參數化**成 config（OSS-generic）。
- **非目標**：不重造外部連結／HTTP 活性檢查（交給 lychee）；不拆成獨立 GitHub repo（單一 PR）；不決定授權／品牌（issue Non-goal）。

## Capabilities

### New Capabilities
- `doc-drift-core`: 語言無關、deterministic 的 doc↔code drift 核心——ctags scoped-identity symbol 集合差集 + in-repo path/coverage primitive + 語言註冊表（Python/bash/C/C++）+ base/HEAD git 物件供給契約 + 誤報雙軌豁免。R-22/R-24/Action 共用。
- `doc-drift-action`: 零設定、可被外部 repo `uses:` 的 GitHub Action——doc-drift 與 moc-alignment 兩 mode、自理 base/head SHA 供給、composite 安裝 ctags、獨立 README、in-repo demo + self-test。

### Modified Capabilities
- `doc-reference`（R-22）: symbol-drift 由 Python-only 裸名改為**語言無關 scoped identity**（限定式精確、裸名保守、歧義 WARN）；改實作為呼叫 `doc-drift-core`，對外語義單調更嚴或等價。
- `moc-alignment`（R-24）: 改實作為呼叫 `doc-drift-core`（共用 path/coverage primitive）；**治理前綴參數化**（預設沿用現值），其餘 FAIL/WARN 判準不變。

## Impact

- **新增核心**：`policy_check/doc_drift/`（refs/paths/symbols/coverage/langs）+ 單元測試。
- **新增 Action**：`.github/actions/doc-drift/`（`action.yml` + 薄 CLI + README）、`examples/doc-drift/` demo fixture、self-test CI job（含 shallow-checkout 情境）。
- **修改規則**：`r22_doc_reference.py`、`r24_moc_alignment.py` refactor 上核心；既有 R-22/R-24 測試續綠。
- **依賴**：執行環境需 `universal-ctags`（CI 安裝；本機已驗 6.2.0）。
- **文件**：主 `README.md`（R-22/R-24 描述、Action 總覽、lychee 互補）、Action `README.md`、`docs/MOC.md`（連結本案產物避免 R-24 orphan）、`CHANGELOG.md [Unreleased]` + 每 phase changelog fragment。
- **release**：feature 先進 `[Unreleased]`；`flat` profile 於 merge 當下 batch bump。
