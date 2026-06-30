## Context

完整設計見 `docs/superpowers/specs/2026-06-30-changelog-fragments-design.md`。本文件只收斂
OpenSpec change 需要的關鍵技術決策與落地邊界。

並行 agent 改共用 `CHANGELOG.md [Unreleased]` 頻繁衝突（#23/#26 合併時實際發生）。改採
per-PR fragment（changesets / towncrier 模式），維持 agent-first（agent 寫碎片、gate 驗碎片）。

## Goals / Non-Goals

**Goals:**
- 並行 PR 各自新增獨立 fragment 檔，零共用行、不衝突、可獨立 merge。
- `R-09` 改驗「本 PR 有 fragment」、`R-04` 不再要求 `[Unreleased]`。
- release 收斂工具產出 Keep-a-Changelog dated 段、清空碎片目錄。

**Non-Goals:**
- 不引入 release-please / semantic-release 自動生成。
- 不改版號語意（`flat` profile PATCH 定義不變）。
- 不在本 repo PR 內改 `hamanpaul/new-project-template`（下游 follow-up）。

## Decisions

### Decision 1 — Hard cutover，行為綁版本，不向下相容
移除 `[Unreleased]` 模型，不做 repo 層 opt-in、不做兩套並存。下游靠 pin engine 版本主動升級，
未升級者用舊行為。避免 issue 警告的「兩套 source 並存混淆」。

### Decision 2 — fragment 位置/檔名：`changelog.d/<issue>-<slug>.md`
towncrier 風格目錄；issue 編號開頭 + 短 slug（例 `changelog.d/24-changelog-fragments.md`）。
不同 issue 天然不撞名、人能讀懂、與 `openspec/changes` 命名一致。空目錄 `.gitkeep` 追蹤。

### Decision 3 — fragment 格式：YAML frontmatter + body
`type`（必填，conventional-commit）、`scope`/`issue`（選填）；frontmatter 後 body = 一條 bullet。
`type` 詞彙與 `R-10` PR title、agent 習慣一致。

### Decision 4 — type → Keep-a-Changelog 段 固定映射
`feat`→Added、`fix`→Fixed、`refactor`/`perf`/`change`→Changed、`remove`→Removed、
`deprecate`→Deprecated、`security`→Security。段順序固定 Added→Changed→Deprecated→Removed→Fixed→Security。
未知 type → collate FAIL。`docs`/`test`/`chore` 非合法 fragment type（該類 PR 走 `skip-changelog`）。

### Decision 5 — release 收斂工具：`policy_check.changelog` 子命令
`python3 -m policy_check.changelog collate --version X.Y.Z --date YYYY-MM-DD`，比照 `policy_check.drift`
分離純邏輯與 I/O 邊緣、可單元測試。讀 `changelog.d/*.md` → 解析 → 分組排序 → 插入 dated 段 → 刪 fragment。

### Decision 6 — 規則行為邊界
- `R-09`：核心改為「`changed_files` 含 `changelog.d/*.md`」；仍受 `code_paths` 觸發、仍可 `skip-changelog`。
- `R-04`：移除 `## [Unreleased]` 必備；保留 `# Changelog` 標頭存在性檢查（不驗 dated 段內部格式）。豁免仍 `policy-exempt:changelog-format`。
- 無新增豁免 label。

## Risks / Trade-offs

- [採用 repo 的 `CHANGELOG.md` 日常無 [Unreleased] 內容] → 待發布內容看 `changelog.d/`；collate 於 release 收斂。
- [既有 [Unreleased] backlog 處理] → 保留歷史內容、移除標頭，不回頭重切舊版段（一次性）。
- [hard cutover 影響下游] → 行為綁版本，未升級 repo 不受影響；升級時依 SOP 採用。

## Migration Plan

1. 新增 `changelog.d/` + collate 工具 + 改 R-09/R-04（含測試）。
2. 本 repo dogfood：建 `changelog.d/`、移除 `[Unreleased]` 標頭、本案用 fragment。
3. 更新 canonical `CLAUDE.md` + README。
4. 下游 repo 升級時依 SOP 採用；`new-project-template` 另案同步。

Rollback：capability 粒度——可單獨回退 collate 工具或 R-09/R-04 改寫。

## Open Questions

- 無。關鍵邊界已於 brainstorm 定稿。實作期小點：既有 [Unreleased] backlog 一次性處理；
  是否提供 `create` fragment helper（傾向 YAGNI 不做）。
