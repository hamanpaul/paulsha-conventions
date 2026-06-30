## Why

本 policy 鼓勵用 `git worktree` 跑並行 agent；多個 PR 同時在共用的 `CHANGELOG.md`
`## [Unreleased]` 區段頂端插 bullet，會頻繁 **merge conflict**——本批 #23 / #26 合併時
實際發生（rebase 需手動解 CHANGELOG 衝突）。業界（changesets / towncrier）以「每 PR 一個
碎片檔」解決，但本案維持 agent-first：agent 寫碎片、gate 驗碎片，不靠「從 commit 自動生成」的 bot。

## What Changes

- 新增 per-PR fragment 模型：待發布記錄改放 `changelog.d/<issue>-<slug>.md`，每 PR 一檔。
- **Hard cutover**：移除共用 `[Unreleased]` 模型，行為綁 engine 版本，不向下相容
  （下游靠 pin 版本 + 升版傳播 SOP 主動升級，未升級者用舊行為）。
- 改 `R-09`：從「`[Unreleased]` 有 bullet」→「本 PR 的 changed files 含 `changelog.d/*.md`」。
- 改 `R-04`：移除 `## [Unreleased]` 必備要求，保留 `# Changelog` 與 Keep-a-Changelog dated 段格式。
- 新增 `python3 -m policy_check.changelog collate`：release 時把 fragment 依 type 收斂成
  Keep-a-Changelog dated 段並清空 `changelog.d/`。
- 本 repo dogfood + 更新 canonical `CLAUDE.md` 與 `README.md`。

## Capabilities

### New Capabilities
- `changelog-fragments`: per-PR fragment 模型——fragment 位置/格式契約、`R-09`（驗本 PR 有 fragment）、
  `R-04`（不再要求 [Unreleased]）、以及 release 收斂工具 `policy_check.changelog collate` 的行為契約。

## Impact

- **新增**：`changelog.d/`（碎片目錄，`.gitkeep` 追蹤）、`policy_check/changelog.py`（collate 工具）。
- **規則**：`R-09`、`R-04` 行為改寫；無新增豁免 label（`skip-changelog` / `policy-exempt:changelog-format` 不變）。
- **測試**：`tests/test_changelog.py`（collate 純邏輯）、`R-09` / `R-04` 既有測試改寫 + 新測試。
- **文件**：canonical `CLAUDE.md`（checklist CHANGELOG 段）、`README.md`（規則表 + fragment 模型 + collate 指令）。
- **本 repo**：建 `changelog.d/`、移除既有 `## [Unreleased]` 標頭（保留歷史內容）、本案自身用 fragment 記錄。
- **範圍外**：`hamanpaul/new-project-template`（另一個 repo）骨架同步屬下游 follow-up。
