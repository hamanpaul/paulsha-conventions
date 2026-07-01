## 1. GitLab provider（pr_context）

- [ ] 1.1 先寫失敗測試 `tests/test_pr_context_gitlab.py`：`gitlab_pr_meta()` 對 `CI_MERGE_REQUEST_*` 映射（labels strip/去空/連續逗號/尾逗號；unset→`[]`；provider=="gitlab"）；`load_pr_meta()` 分派優先序（GitLab>GitHub event>空 `{}`）
- [ ] 1.2 實作 `pr_context.gitlab_pr_meta()` + `load_pr_meta()`（回恆為 dict、含 `provider`）
- [ ] 1.3 測試轉綠；GitHub 既有 `pr_meta_from_event` 行為不變

## 2. changed_files 拆 SHA / branch 路徑

- [ ] 2.1 先寫失敗測試 `tests/test_pr_context_changed_files.py`：SHA base → `git diff <sha>...HEAD`（不含 origin/）；branch base → `origin/<b>...HEAD`
- [ ] 2.2 改 `changed_files` 支援 SHA / branch 兩路徑（介面加判定或分參數）
- [ ] 2.3 測試轉綠

## 3. cli.py 接 load_pr_meta

- [ ] 3.1 `build_context` 改用 `pr_context.load_pr_meta()`（取代直呼 `load_event_payload`+`pr_meta_from_event`）；把 `provider` 帶入 `RuleContext`（新增欄位）
- [ ] 3.2 全 suite 綠；`python3 -m policy_check --repo .` 行為不變（GitHub/本地路徑）

## 4. R-12 GitLab NA

- [ ] 4.1 先寫失敗測試 `tests/test_rule_r12_gitlab_na.py`：`ctx.provider=="gitlab"` → R-12 NA（PASS，訊息標明）；GitHub/本地既有行為不變
- [ ] 4.2 `r12_branch_source.py`：provider==gitlab 早退 NA
- [ ] 4.3 測試轉綠（既有 R-12 測試續綠）

## 5. R-23 pip-mode + R-08 mode 列舉

- [ ] 5.1 先寫失敗測試 `tests/test_rule_r23_pip_mode.py`：mode:pip installed==policy_version → PASS（含 `-fix.N`↔`.postN`）；不符 → FAIL；未安裝 → FAIL；**mode:pip + repo 未設 + 不符 → FAIL（非 NA）**；mode:workflow/未設 → 現行行為（既有 R-23 測試續綠）
- [ ] 5.2 `r23_engine_pin_attestation.py`：mode 先判、pip 分支獨立於 repo；pip attestation 用 `importlib.metadata.version("policy-check")` + 內部 PEP 440 正規化比對；fail-closed
- [ ] 5.3 `r08_policy_config_schema.py`：驗 `conventions_engine.mode ∈ {workflow, pip}`（未知值 FAIL）；補測試
- [ ] 5.4 測試轉綠 + 全 R-23/R-08 既有測試續綠

## 6. 版本 lockstep

- [ ] 6.1 先寫失敗測試 `tests/test_version_lockstep.py`：`pyproject [project].version == VERSION 檔 == .paul-project.yml policy_version`
- [ ] 6.2 確認三者一致（現況 1.0.10）；測試轉綠

## 7. wheel 離線 smoke + package-data 稽核

- [ ] 7.1 稽核 `pyproject` package-data 涵蓋所有 runtime 非-.py 資產（`policy_check/data/**` 等）；`tests/fixtures` 不被打包
- [ ] 7.2 `tests/test_wheel_offline.py`（slow/packaging gate，以 `PACKAGING=1` 或 marker）：build wheel → `pip download` 相依閉包到 vendor → 乾淨 venv `pip install --no-index --find-links <vendor>` → 跑 `policy-check --repo <fixture>` 斷言可執行
- [ ] 7.3 於 packaging 環境驗證通過（一般 pytest 不跑此 gate）

## 8. 文件 + changelog

- [ ] 8.1 `README.md` 補「離線 pip 安裝 + GitLab CI gate」段：vendored-wheels 離線安裝、`.gitlab-ci.yml` 範例（`merge_request_event` rule、`GIT_DEPTH: 0`、`apt-get install universal-ctags`、`conventions_engine.mode: pip`）、build-time 需網路 vs gate-time 離線界線、發行管道選型 follow-up
- [ ] 8.2 changelog fragment `changelog.d/20-gitlab-pip.md`（type: feat, issue: 20）

## 9. 收尾

- [ ] 9.1 全 suite 綠（`python3 -m pytest -q`，wheel smoke 除外由 gate 跑）
- [ ] 9.2 `python3 -m policy_check --repo .` 無 fail
- [ ] 9.3 `openspec validate gitlab-internalization --strict` 通過
- [ ] 9.4 `docs/MOC.md` 連結本 spec/plan（消 R-24 orphan）
