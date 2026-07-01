## Context

引擎現只讀 GitHub（`GITHUB_EVENT_PATH`）、以 workflow `uses:` pin 做 R-23 attestation、以 GitHub Actions reusable workflow 發行。要在公司 GitLab 以離線 pip 套件當 gate，需補 MR context 輸入、pip-mode attestation、離線可安裝 wheel。完整設計（含 D1–D11、對抗式覆審修正）見 `docs/superpowers/specs/2026-07-01-gitlab-internalization-design.md`。

## Goals / Non-Goals

**Goals:**
- GitLab merge_request pipeline 下 R-10/11/17 內容等效、R-12 明確 NA。
- 顯式 `conventions_engine.mode: pip` 下 R-23 以已安裝版本 attestation、fail-closed。
- wheel 之 Python 相依離線可裝（vendored wheels）、離線可跑，真 smoke 驗證。

**Non-Goals:**
- 不選發行管道；不改規則判定語義；不動 GitHub 路徑；零 rule_id/label 變動。

## Decisions

- **D1 provider 分派**：`load_pr_meta()` 回恆為 dict（空為 `{}` 非 None）；偵測 GitLab(`CI_MERGE_REQUEST_IID`) > GitHub(`GITHUB_EVENT_PATH`) > 空；meta 帶 `provider`。
- **D2 R-12 GitLab NA**：base=main+feature/wt 為 hamanpaul 專屬，provider==gitlab 時 R-12 回 NA（config 驅動 branch 規則列 follow-up），不假稱等效。
- **D3 changed_files 拆路徑**：`CI_MERGE_REQUEST_DIFF_BASE_SHA` → `git diff <sha>...HEAD`（不加 origin/）；否則 `origin/<target>...HEAD`。防無效 ref 靜默 `[]` 導致 diff 規則假 PASS。
- **D4 pipeline source**：`.gitlab-ci.yml` 限 `$CI_PIPELINE_SOURCE == "merge_request_event"`；空 meta 時 log 標「PR 面向規則略過」。
- **D5 mode 求值序**：`mode == "pip"` 先判、獨立於 `repo`（repo 空照跑不早退）；否則現行 workflow 路徑。
- **D6 pip attestation**：`importlib.metadata.version("policy-check")` ↔ `policy_version`，PEP 440 正規化比對（`-fix.N`↔`.postN`，內部小函式，不引入 packaging）；未安裝/不符 FAIL。
- **D7 R-08**：`conventions_engine.mode ∈ {workflow, pip}`，未知值 FAIL。
- **D8 版本 lockstep**：`pyproject [project].version` 入 release-bump 檔集 + `pyproject==VERSION==policy_version` 測試；wheel version 用合法 PEP 440。
- **D9 真離線 smoke**：build wheel → `pip download` 相依閉包 → 乾淨 venv `pip install --no-index --find-links` → run；slow/packaging gate。
- **D10 ctags 系統前置**：wheel 自足限 Python 相依；`universal-ctags` GitLab CI apt-get。

## Risks / Trade-offs

- R-12 NA 犧牲 GitLab 的分支來源把關（follow-up 補 config）；換取誠實、不誤判、scope 最小。
- pip-mode PEP 440 正規化須與 policy `-fix.N` 語法對映一致，否則 hotfix 版誤判。
- 真 smoke 需 build 工具 + 網路取相依閉包（build 階段），gate 階段離線；一般 pytest 不跑（gate 標記）。
