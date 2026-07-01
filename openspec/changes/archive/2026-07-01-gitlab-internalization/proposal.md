## Why

paulsha-conventions 目前只能在 GitHub Actions（reusable workflow）跑；公司內部專案在 GitLab，且此機制可能導入內部。issue #20 要讓引擎能以**可離線安裝的 pip 套件**在 GitLab CI 上作為 gate 執行。規則邏輯本就 platform-agnostic（純 git-level），本案只補「輸入來源（MR context）」與「發行/attestation 形態」兩層，規則判定語義不改。

對應設計 spec：`docs/superpowers/specs/2026-07-01-gitlab-internalization-design.md`（v2，含對抗式覆審修正）。

## What Changes

- **chunk 2 — GitLab provider**（`pr_context.py`）：`load_pr_meta()` provider 分派（GitLab `CI_MERGE_REQUEST_*` / GitHub event / 空 `{}`）；labels strip+去空；`changed_files` 拆 SHA（`git diff <sha>...HEAD`）/ branch（`origin/<b>...HEAD`）兩路徑防假 PASS；**R-12 在 GitLab 標 NA**（分支慣例 hamanpaul 專屬，不硬套）；`.gitlab-ci.yml` 須限 `merge_request_event`。R-10/11/17 platform-agnostic 不改。
- **chunk 3 — R-23 pip-mode**：顯式 `conventions_engine.mode`（`workflow` 預設＝現行；`pip`＝新）；**mode 先判、獨立於 `repo`**（防 fail-open）；pip 態比對已安裝 `policy-check` 版本 ↔ `policy_version`，用 PEP 440 正規化（`-fix.N`↔`.postN`）而非 raw 字串，未安裝/不符 **fail-closed FAIL**；R-08 驗 `mode` 列舉。GitHub workflow 路徑零回歸。
- **chunk 1a — wheel 硬化 + 真離線 smoke**：離線＝wheel + vendored 相依 wheels（`pip download` 閉包 + `pip install --no-index --find-links`）；smoke 真 build+download+install+run；`universal-ctags` 列系統前置；`pyproject [project].version` 入 release-bump 檔集 + `pyproject==VERSION==policy_version` lockstep 測試。
- **非目標**：不選內部發行管道（Artifactory/PyPI/registry）→ follow-up；不改規則判定語義；不動 GitHub 路徑；零 rule_id/label 變動。

## Capabilities

### New Capabilities
- `gitlab-ci-gate`: 引擎作為**離線 pip 套件**在 GitLab **merge_request** pipeline 當 gate——MR context provider（R-10/11/17 內容等效、R-12 provider-aware NA、labels/changed_files 正確處理）、R-23 **pip-mode** attestation（顯式 `mode: pip`、fail-closed、PEP 440 正規化版本比對）、離線 wheel + vendored 相依安裝（`universal-ctags` 為系統前置）。

### Modified Capabilities
（無獨立 modified capability spec：R-12（GitLab NA）與 R-23（pip-mode）的行為變更收斂於 `gitlab-ci-gate` 需求內；GitHub 既有路徑零回歸。）

## Impact

- **修改（碼）**：`policy_check/pr_context.py`（GitLab provider + changed_files 拆路徑）、`policy_check/cli.py`（用 `load_pr_meta`）、`policy_check/rules/r23_engine_pin_attestation.py`（pip-mode）、`policy_check/rules/r12_branch_source.py`（GitLab NA）、`policy_check/rules/r08_policy_config_schema.py`（`conventions_engine.mode` 列舉）。
- **修改（config/build/docs）**：`pyproject.toml`（版本 lockstep 認知）、`README.md`（離線安裝 + `.gitlab-ci.yml` 範例）、測試多支。
- **相依**：runtime 不新增（用 stdlib `importlib.metadata`；PEP 440 正規化以內部小函式處理，不引入 `packaging`）；`universal-ctags` 為既有系統前置（GitLab CI 需 apt-get）。
- **版本**：flat profile，merge 後 PATCH bump 1.0.10 → 1.0.11（與 nits + #35 collate）。
