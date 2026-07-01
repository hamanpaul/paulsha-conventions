# gitlab-ci-gate Specification

## Purpose
TBD - created by archiving change gitlab-internalization. Update Purpose after archive.
## Requirements
### Requirement: GitLab MR context provider

引擎 SHALL 在 GitLab merge_request pipeline 下，從 `CI_MERGE_REQUEST_*` 環境變數取得與 GitHub PR 等效的 MR context（title/body/labels/source·target branch），供 R-10/R-11/R-17 使用。provider 分派回傳恆為 dict（無 context 時為 `{}`，非 None）。

#### Scenario: GitLab MR 提供等效 context
- **WHEN** `CI_MERGE_REQUEST_IID` 存在且設有 `CI_MERGE_REQUEST_TITLE`/`_DESCRIPTION`/`_LABELS`/`_SOURCE_BRANCH_NAME`/`_TARGET_BRANCH_NAME`
- **THEN** `load_pr_meta()` 回傳的 `pr_title`/`pr_body`/`pr_labels`/`pr_head_ref`/`pr_base_ref` 與 GitHub PR 語義等效，且 `provider == "gitlab"`

#### Scenario: labels 逗號分隔須 strip 去空
- **WHEN** `CI_MERGE_REQUEST_LABELS` 為 `"wip, policy-exempt:docs-sync ,"`（含空白與尾逗號）
- **THEN** `pr_labels == ["wip", "policy-exempt:docs-sync"]`（每 token strip、丟棄空 token），使 exemption label 比對命中

#### Scenario: 非 MR pipeline 回退空 context
- **WHEN** 既非 GitLab MR（無 `CI_MERGE_REQUEST_IID`）亦非 GitHub event
- **THEN** `load_pr_meta()` 回 `{}`，PR 面向規則以「非 PR context」處理（與現行相同）

### Requirement: changed_files 依 base 類型解析

`changed_files` SHALL 依 base 是 commit SHA 或 branch name 走不同 diff 命令，避免把 SHA 塞入 `origin/<ref>` 樣板產生無效 ref 而靜默回空清單（導致 diff 依賴型規則假 PASS）。

#### Scenario: base 為 SHA 不加 origin 前綴
- **WHEN** GitLab 提供 `CI_MERGE_REQUEST_DIFF_BASE_SHA`
- **THEN** 以 `git diff <sha>...HEAD` 取變更檔（不前綴 `origin/`）

#### Scenario: base 為 branch name 沿用 origin
- **WHEN** 只有 target branch name（無 diff base SHA）
- **THEN** 以 `git diff origin/<target>...HEAD` 取變更檔

### Requirement: R-12 在 GitLab provider 下標 NA

R-12（分支來源）的 `main` + `feature/*`/`wt/*` 慣例為 hamanpaul 專屬，SHALL 不套用於任意 GitLab 專案：provider 為 GitLab 時 R-12 回 NA（PASS，訊息標明慣例不適用），不得誤判為 FAIL 或靜默 no-op PASS。GitHub 既有行為不變。

#### Scenario: GitLab 下 R-12 為 NA
- **WHEN** provider 為 GitLab
- **THEN** R-12 回 NA（PASS），訊息標明分支來源慣例不適用於 GitLab

### Requirement: R-23 pip-mode attestation（fail-closed）

R-23 SHALL 支援顯式 `conventions_engine.mode`：`pip` 時比對已安裝 `policy-check` distribution 版本 ↔ `policy_version`，且求值序上 `mode == "pip"` 先判、獨立於 `conventions_engine.repo`（repo 未設也照跑、不早退 NA）。版本比對用 PEP 440 正規化（policy `-fix.N` ↔ `.postN`）。GitHub 的 `workflow`（預設/未設）路徑行為不變。

#### Scenario: 已安裝版本相符則 PASS
- **WHEN** `mode: pip` 且已安裝 `policy-check` 版本正規化後等於 `policy_version`（含 `-fix.N`↔`.postN`）
- **THEN** R-23 PASS

#### Scenario: 版本不符則 FAIL
- **WHEN** `mode: pip` 且已安裝版本與 `policy_version` 不符
- **THEN** R-23 FAIL

#### Scenario: 套件未安裝 fail-closed
- **WHEN** `mode: pip` 但 `policy-check` 未安裝（`PackageNotFoundError`）
- **THEN** R-23 FAIL（明確訊息，不 fail-open、不回 NA）

#### Scenario: pip 態獨立於 repo 未設
- **WHEN** `mode: pip`、`conventions_engine.repo` 未設、且版本不符
- **THEN** R-23 FAIL（不因 repo 未設而早退 NA）

#### Scenario: 未知 mode 值被 R-08 擋
- **WHEN** `conventions_engine.mode` 為列舉外的值（如 `pipp`）
- **THEN** R-08 FAIL（config schema 錯誤，不靜默落回 workflow）

### Requirement: 離線可安裝、可執行的 wheel

引擎 SHALL 能以「wheel + vendored 相依 wheels」離線安裝並執行；`pip install --no-index <wheel>`（無相依來源）不足以完成安裝，須以 `--find-links <vendor>` 提供相依閉包。`universal-ctags` 為系統前置（非 pip 相依）。`pyproject [project].version` 與 `VERSION`/`policy_version` SHALL 鎖步一致。

#### Scenario: 離線安裝後可執行
- **WHEN** 於乾淨 venv 以 `pip install --no-index --find-links <vendor> policy-check==<v>` 安裝（vendor 內含相依閉包）
- **THEN** `policy-check --repo <repo>` 可在無外網下執行並產出報告

#### Scenario: 版本鎖步守恆
- **WHEN** 檢查 `pyproject [project].version`、`VERSION` 檔、`.paul-project.yml` 的 `policy_version`
- **THEN** 三者一致（任一漏 bump 由 lockstep 測試擋下）

