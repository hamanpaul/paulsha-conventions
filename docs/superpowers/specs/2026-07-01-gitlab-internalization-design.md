# 引擎內部化 / GitLab 發行（可離線 pip 套件）— 設計 spec（v2，含對抗式覆審修正）

> 制定日期：2026-07-01 · profile: flat · 目標版本：1.0.11（PATCH，與 nits/#35 同批）
> 分支：`feature/20-gitlab-pip` · 對應 issue #20

## 1. 背景與動機

paulsha-conventions 目前只能在 GitHub Actions 跑。內部專案在公司 GitLab，且此機制可能導入內部。issue #20 要讓引擎能以**可離線安裝的 pip 套件**在 GitLab CI 上作為 gate 執行。規則邏輯本就 platform-agnostic（純 git-level），本案只補「輸入來源（MR context）」與「發行/attestation 形態」兩層。

**本次範疇（使用者定案）：** chunk 2（GitLab provider）+ chunk 3（R-23 pip-mode，顯式 `conventions_engine.mode`）+ chunk 1a（wheel 硬化 + 真 build+install+run smoke）。**發行管道選型**（Artifactory/PyPI/registry）為公司決策 → follow-up。

> v2 依 Claude 三視角對抗式覆審修正 1 critical + 8 important（離線相依、R-12 適用性、changed_files SHA 路徑、labels strip、provider 偵測、pip-mode PEP 440、mode 求值序、ctags 外部相依、pyproject 版本守恆）。

## 2. Goals / Non-Goals

**Goals**
- G1：GitLab **merge_request** pipeline 下，R-10/R-11/R-17 取得與 GitHub PR 等效的 title/body/labels/source·target；R-12 明確標 NA（見 D2）。
- G2：引擎以 pip 套件被消費時（顯式 `conventions_engine.mode: pip`），R-23 以「已安裝 `policy-check` 版本 ↔ `policy_version`」做 attestation，**fail-closed**。
- G3：`python -m build` 產出的 wheel，其 **Python 相依可離線安裝**（wheel + vendored 相依 wheels），並能離線跑 `policy-check`（真 build+download+install+run smoke 驗證）。`universal-ctags` 為**外部系統相依**（非 pip 可裝），列為 GitLab gate 前置。

**Non-Goals**
- N1：不選定內部發行管道；不寫實際部署。
- N2：不改規則**判定語義**；R-10/R-11/R-17 只換輸入來源，R-12 在 GitLab 標 NA（不硬套 hamanpaul 分支慣例），R-23 只多一種 attestation 形態。
- N3：不動 GitHub 既有路徑（GitHub Actions / workflow `uses:` pin 的 R-23 行為零回歸）。
- N4：不新增/合併/改號 rule_id 或 exemption label。

## 3. 詳細設計

### chunk 2 — `pr_context.py` GitLab provider

現況：`load_event_payload()` 讀 `GITHUB_EVENT_PATH`；`pr_meta_from_event()` 取 pr_*；`changed_files(base_ref, root)` 固定 `git diff origin/<base>...HEAD`。

**D1 — provider 分派 `load_pr_meta() -> dict`**（`build_context` 唯一呼叫點；**回傳恆為 dict，永不 None**）：
1. GitLab：`CI_MERGE_REQUEST_IID` 存在 → `gitlab_pr_meta()`。
2. GitHub：`GITHUB_EVENT_PATH` 存在 → `pr_meta_from_event(load_event_payload())`。
3. 皆無 → `{}`（回退 CLI args，與現行相同）。
- meta 內含 `provider ∈ {"github","gitlab", None}` 供 R-12 判定。

**`gitlab_pr_meta()` 映射：**
- `pr_title` ← `CI_MERGE_REQUEST_TITLE`
- `pr_body` ← `CI_MERGE_REQUEST_DESCRIPTION`
- `pr_labels` ← `[t.strip() for t in CI_MERGE_REQUEST_LABELS.split(",") if t.strip()]`（**每 token strip、丟棄空 token**；已在 MR context 故 unset/空 → `[]`（非 None），與 GitHub「PR-無-label」語義齊）
- `pr_base_ref` ← target branch（見 D3）
- `pr_head_ref` ← `CI_MERGE_REQUEST_SOURCE_BRANCH_NAME`
- `provider` ← `"gitlab"`

**D2 — R-12 在 GitLab 標 NA（重要修正）：** R-12 的 base==`main` + `feature/*`/`wt/*` 是 hamanpaul 專屬慣例，無法「只換輸入來源」等效於任意 GitLab 專案（master 預設 → 靜默 no-op；非 feature 命名 → 全誤 FAIL）。故：**provider==gitlab 時 R-12 回 NA（PASS，訊息標明分支慣例不適用）**。config 驅動的可調 branch 規則列為 follow-up。R-10/R-11/R-17 不受影響（純內容比對，platform-agnostic）。

**D3 — changed_files 拆 SHA / branch 兩路徑（重要修正）：** 現行只會組 `origin/<base>...HEAD`，把 raw SHA 丟進去會變無效 ref → 靜默 `[]` → R-09/R-18/R-24 假 PASS。改：
- GitLab 有 `CI_MERGE_REQUEST_DIFF_BASE_SHA` → `git diff <sha>...HEAD`（**不加 `origin/` 前綴**）。
- 否則（branch name）→ `git diff origin/<base>...HEAD`（現行）。
- `changed_files` 介面加「base 是 SHA 還是 branch」的判定（或分兩參數）；測試涵蓋 SHA 路徑不被 `origin/` 汙染。
- 文件要求 GitLab job `GIT_DEPTH: 0`（或 fetch target），避免 shallow 缺 base。

**D4 — pipeline source 要求（重要修正）：** `CI_MERGE_REQUEST_IID` 只在 **merge_request pipeline** 有；branch pipeline 會落到空 meta → R-10/11/17 退回「非-PR PASS」→ 假綠 gate。故 `.gitlab-ci.yml` 範例**必須**限定 `rules: - if: $CI_PIPELINE_SOURCE == "merge_request_event"`；且分派落回空 meta 時於 log 標「非 MR context，PR 面向規則略過」以免誤讀為通過。

### chunk 3 — R-23 pip-mode（顯式 `conventions_engine.mode`）

現況：R-23 讀 `conventions_engine.repo`，`if not repo → NA`；否則掃 workflow `uses:` 比對 ref（tag/SHA+尾註）↔ `policy_version`。

**D5 — 求值序：mode 先判，pip 獨立於 repo（重要修正，防 fail-open）：**
```
mode = (conventions_engine.mode or "workflow")
if mode == "pip":
    → pip attestation（完全獨立於 conventions_engine.repo；repo 空也照跑，不早退 NA）
else:  # "workflow"（預設/未設）
    → 現行 repo 早退 + workflow uses: 掃描（GitHub 行為零改動）
```

**D6 — pip attestation：**
- 取已安裝 distribution 版本：`importlib.metadata.version("policy-check")`（distribution 名 = pyproject `[project].name` = `policy-check`；已驗）。
- 比對用**版本正規化**而非 raw 字串（重要修正，處理 `-fix.N`）：定義 `_canon(v)`：policy 語法 `X.Y.Z[-fix.N]` ↔ 安裝版 PEP 440 的規範對映——`-fix.N` → `.postN`（wheel `[project].version` 亦以 PEP 440 形式表示，見 D8）；兩側各自 `_canon` 後比較。不引入 `packaging` 相依（避免擴大離線 closure），以內部小正規化函式處理（策略：把 `-fix.N`→`.postN`、`.postN`→`-fix.N` 雙向對映後字串相等）。
- 結果：相符 PASS；不符 FAIL（`installed policy-check v{A} but policy_version declares {B}`）；`importlib.metadata.PackageNotFoundError` → **FAIL**（明確訊息，不 fail-open）。
- pip-mode 下**不掃 workflow**。

**D7 — R-08 schema：** 驗 `conventions_engine.mode`（若有）∈ `{workflow, pip}`；未知值（typo `pipp`）→ R-08 FAIL（config 錯誤，不靜默落回 workflow）。

### chunk 1a — wheel 硬化 + 真離線 smoke + 文件

現況：`pyproject.toml` 已有 build-system/project/scripts/package-data（`policy_check.data` = `*.yml`；覆審 confirm package-data 已涵蓋唯一 runtime 非-.py 資產、`tests/fixtures` 正確排除）。

**D8 — 版本守恆（重要修正）：** pip-mode 使 pyproject `[project].version` 成為下游 gate 正確性的 load-bearing 值。故：
- `pyproject.toml` `[project].version` 明列入 release-bump 檔集（§6），與 `VERSION`/`policy_version` 鎖步。
- 新增 self-guard 測試：`pyproject [project].version == VERSION 檔內容 == .paul-project.yml policy_version`（三者一致），漏 bump 立即紅。
- wheel version 必須合法 PEP 440；hotfix 以 `X.Y.Z.postN` 表示（與 D6 對映一致）。

**D9 — 真離線 smoke（`tests/test_wheel_offline.py`，critical 修正）：** `pip install --no-index <wheel>` 會因取不到 `PyYAML` 而失敗。正確離線 = **wheel + vendored 相依 wheels**：
1. `python -m build --wheel` 產 engine wheel（build 階段可連網取 build backend；此為建置環境，非 gate 環境）。
2. `pip download --dest <vendor> policy-check==X.Y.Z`（或對 wheel `pip download -r`）取得**完整相依閉包**（PyYAML +…）。
3. 乾淨 venv → `pip install --no-index --find-links <vendor> policy-check==X.Y.Z`（`--no-index` 保證不連外，`--find-links` 供本地相依）。
4. venv 內跑 `policy-check --repo <fixture>`，斷言退出碼/輸出合理。
- 標 slow / packaging gate（`PACKAGING=1` 或 marker），一般 pytest 不跑。

**D10 — ctags 外部相依（重要修正）：** wheel「自足」僅限 **Python 相依**；R-22/R-24 的 symbol 分析 shell out 到 `universal-ctags` binary（pip 裝不了）。故文件明訂 `universal-ctags` 為 GitLab gate 系統前置（`.gitlab-ci.yml` 範例 `apt-get install -y universal-ctags`，與 GitHub self-test 同）；「self-sufficient」宣稱限縮為「Python 相依離線可裝」。

**D11 — 文件：** README 補「離線 pip 安裝 + GitLab CI gate」段：vendored-wheels 離線安裝、`.gitlab-ci.yml` 範例（merge_request rule、`GIT_DEPTH: 0`、apt-get ctags、`conventions_engine.mode: pip`）、build-time 需網路 vs gate-time 離線的界線。**發行管道選型**明列 follow-up。

## 4. 架構與邊界（isolation）

- `pr_context.py`：GitLab provider 為純函式；`load_pr_meta()` 唯一分派；GitHub 路徑零改。changed_files 拆 SHA/branch 兩路徑。
- `r23`：pip-mode 是 `check()` 內依 mode 的第一層分岔；workflow 路徑原封不動。
- wheel/smoke：純打包/測試/文件，無 runtime 碼耦合。
- R-12：provider-aware（gitlab→NA）；GitHub 行為不變。

## 5. 測試策略

1. `test_pr_context_gitlab.py`：`gitlab_pr_meta()` 映射（labels strip/去空/連續逗號/尾逗號、unset→[]、provider 值）；`load_pr_meta()` 分派優先序 + 空 meta 為 `{}`；GitHub 既有行為續綠。
2. `test_pr_context_changed_files.py`：SHA base → `git diff <sha>...HEAD`（不含 origin/）；branch base → `origin/<b>...HEAD`；覆蓋假 PASS 回歸。
3. `test_rule_r12_gitlab_na.py`：provider==gitlab → R-12 NA；GitHub 既有行為不變。
4. `test_rule_r23_pip_mode.py`：mode:pip installed==policy_version → PASS（含 `-fix.N`↔`.postN`）、不符 → FAIL、未安裝 → FAIL、**mode:pip + repo 未設 + 版本不符 → FAIL（非 NA）**；mode:workflow/未設 → 現行行為（既有 R-23 測試續綠）；R-08 驗 mode 列舉（未知值 FAIL）。
5. `test_version_lockstep.py`：pyproject version == VERSION == policy_version。
6. `test_wheel_offline.py`：真 build+download+install(`--no-index --find-links`)+run（slow/packaging gate）。
7. 全 suite 綠；`python3 -m policy_check --repo .` 無 fail（本 repo `conventions_engine.mode` 未設 → workflow 路徑；repo="" → R-23 NA，pip-mode 不影響）。

## 6. Rollout / 版本

- feature → 併入本批 PATCH **1.0.11**（與 nits + #35 collate）。release-bump 檔集**含 `pyproject.toml` [project].version**（D8）。
- changelog fragment `changelog.d/20-gitlab-pip.md`（type: feat, issue: 20）。
- PR body `Closes #20`。發行管道選型另開 follow-up issue 追蹤。

## 7. 風險與緩解

- **R1 離線相依**（critical）→ D9 vendored wheels + `--find-links`；smoke 真裝真跑。
- **R2 R-12 誤判**→ D2 GitLab NA + follow-up config。
- **R3 changed_files 假 PASS**→ D3 SHA/branch 拆路徑 + 測試。
- **R4 labels 失配**→ strip/去空 + 測試。
- **R5 branch pipeline 假綠**→ D4 merge_request rule + log。
- **R6 pip-mode fail-open / `-fix.N`**→ D5 mode 先判 + D6 正規化比對 + D7 R-08 列舉。
- **R7 ctags 缺**→ D10 系統前置文件。
- **R8 pyproject 漏 bump**→ D8 lockstep 測試 + release 檔集。
- **R9 發行管道未定**→ follow-up，不阻擋 chunk 2/3/1a。

## 8. Self-review 檢核

- 無 TBD／placeholder。9 個 blocking findings 皆有對應 D2–D10。
- Non-goals 明確；GitHub 路徑零回歸；R-12 語義誠實標 NA（不假稱等效）。
- chunk 2/3/1a 邊界清楚、可分別驗收。
