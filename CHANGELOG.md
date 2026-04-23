# Changelog

本專案所有重大變更都會記錄在此檔案。

格式基於 [Keep a Changelog 1.1.0](https://keepachangelog.com/zh-TW/1.1.0/)，
本專案遵循 hamanpaul project policy v1.0.0。

## [Unreleased]

### Changed
- Rename repo from `paul-project-conventions` to `paulsha-conventions`；更新 README、四份 agent convention files 與 fixtures 的 `managed-by` 與 `uses:` 參照

### Added
- **R-01 ~ R-16 完整規則實作**（TDD 覆蓋 + fixtures）
  - R-01: README.md 存在性檢查
  - R-02: README.md 必備段落（Install / Usage / Version）
  - R-03: CHANGELOG.md 存在性檢查
  - R-04: CHANGELOG.md 格式（Keep-a-Changelog 1.1.0 schema + `[Unreleased]` section）
  - R-05: VERSION 存在性檢查
  - R-06: VERSION 語意檢查（`<MAJOR>.<MINOR>.<PATCH>[-fix.N]`）
  - R-07: VERSION 與最新 tag 一致性（除非 PR 帶 `release:*` label）
  - R-08: `.paul-project.yml` 存在性與完整性（`policy_profile` / `policy_version` 必填）
  - R-09: Code 變動必有 CHANGELOG entry（code_paths 涵蓋檔案變動時，`[Unreleased]` 必須有新增 entry，或 PR 帶 `skip-changelog` + 理由）
  - R-10: PR title conventional-commit 格式（`type(scope): subject` 或 `type: subject`）
  - R-11: PR body checkbox 全勾檢查（帶 `wip` label 時自動通過）
  - R-12: 分支來源正確性（目標=main 要求來源 `feature/*`；目標=`feature/*` 要求來源 `wt/<feature>/*`）
  - R-13: Agent convention files 存在性（`CLAUDE.md` / `AGENTS.md` / `GEMINI.md` / `.github/copilot-instructions.md`）
  - R-14: Agent files policy 版本一致性（四份檔案 `policy_version` 必須與 `.paul-project.yml` 一致）
  - R-15: Caller workflow ref 鎖定檢查（`uses:` 必須指向 tag / SHA，禁止 branch ref 如 `@main`）
  - R-16: CLI help 與 docs 同步檢查（`.paul-project.yml.cli` 宣告的 command，實跑 help 輸出必須與 marker 區塊字元一致）
- **Reusable workflow**：`.github/workflows/policy-check.yml`（下游 repo 直接 `uses:` 呼叫）
- **Composite action**：`.github/actions/policy-check/action.yml`（可獨立使用或被 workflow 呼叫）
- **Helper script**：`scripts/update-cli-help.sh`（本地更新 CLI help marker 區塊，配合 R-16）
- **Agent convention files 完整 checklist**（zh-TW）：
  - 動工前 / 改 code 時 / 改版號時 / claim done 前分階段檢查清單
  - 禁止事項明列（不可發明新豁免 label、不可直接 commit 到 main 等）
  - Exemption Labels 白名單（`policy-exempt:*` / `skip-changelog` / `wip`）
- **使用者文件 README.md 完整化**（zh-TW）：
  - 專案背景與問題定位
  - R-01~R-16 規則總覽表（含豁免 label）
  - CI 整合範例（reusable workflow caller）
  - Helper scripts 使用說明
  - 新專案 bootstrap 流程

### Changed
- CHANGELOG.md 格式改為 zh-TW 敘述，拆分明細項目（取代過度籠統的兩條 Added）
- 四份 agent files 內容完全同步（`CLAUDE.md` / `AGENTS.md` / `GEMINI.md` / `.github/copilot-instructions.md`）

### Fixed
- 無（baseline 建立階段）
- reusable workflow 不再對下游 repo 執行 `pip install -e .`；改為僅安裝 action runtime 相依，並讓 composite action 直接從自身 source tree 載入 `policy_check`
- **reusable workflow action 解析問題**：移除 `uses: ./.github/actions/policy-check`（在被呼叫 workflow 中此路徑解析自 caller repo，導致 action-not-found）；改為顯式 checkout `hamanpaul/paulsha-conventions` 至 `.policy-engine/` 並直接呼叫 `run.sh`
- **interpreter 不一致**：`run.sh` 移除對 `${WORKSPACE}/.venv/bin/python` 的優先使用；統一使用 `setup-python` 設置的 `python3`，確保安裝與執行使用同一直譯器
- **README 敘述**：更新 CI workflow 說明，反映實際的 policy engine checkout + 安裝流程
- **reusable workflow policy engine 版本漂移**：`Checkout policy engine` 步驟加入 `ref: ${{ github.workflow_sha }}`，確保 policy engine 版本與呼叫者所鎖定的 workflow 版本一致，消除未鎖定時永遠抓 main branch 的風險；同步新增回歸測試 `test_reusable_workflow_policy_engine_checkout_is_pinned`
