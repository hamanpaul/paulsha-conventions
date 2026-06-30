## ADDED Requirements

### Requirement: per-PR changelog fragment 取代共用 [Unreleased]

待發布的 changelog 記錄 SHALL 以每 PR 一個 fragment 檔表示，置於 `changelog.d/`，
檔名為 `<issue>-<slug>.md`。fragment SHALL 以 YAML frontmatter 宣告 `type`（必填，
conventional-commit 詞彙），選填 `scope` / `issue`；frontmatter 後的 body 為一條 changelog 描述。
本模型為 hard cutover：採用此版的 repo SHALL NOT 再以共用 `## [Unreleased]` 區段累積待發布記錄。

#### Scenario: 並行 PR 各自的 fragment 互不衝突
- **WHEN** 兩個不同 issue 的 PR 各自新增 `changelog.d/<issue>-<slug>.md`
- **THEN** 兩個 fragment 為不同檔案、零共用行，可各自獨立 merge 而不產生 changelog 衝突

#### Scenario: fragment 缺少必填 type 為非法
- **WHEN** 某 fragment 的 frontmatter 缺少 `type`
- **THEN** 收斂工具視其為非法並回報錯誤

### Requirement: R-09 改驗本 PR 是否附 fragment

當 `code_paths` 涵蓋的檔案於本次變更有異動時，`R-09` MUST 改以「本 PR 的 changed files
是否含 `changelog.d/` 下的 fragment」判定，而非檢查 `[Unreleased]` 是否有 bullet。
帶 `skip-changelog` label 時 MUST 回報 SKIP；無 code 變動時 MUST 回報 PASS。

#### Scenario: code 變動且附 fragment
- **WHEN** 本 PR 變更了 `code_paths` 檔案，且 changed files 含一個 `changelog.d/*.md`
- **THEN** R-09 回報 PASS

#### Scenario: code 變動但未附 fragment
- **WHEN** 本 PR 變更了 `code_paths` 檔案，但 changed files 不含任何 `changelog.d/*.md`
- **THEN** R-09 回報 FAIL（除非帶 `skip-changelog` label）

#### Scenario: skip-changelog 豁免
- **WHEN** 本 PR 變更了 `code_paths` 檔案但帶 `skip-changelog` label
- **THEN** R-09 回報 SKIP

### Requirement: R-04 不再要求 [Unreleased] 區段

`R-04` MUST NOT 再要求 `CHANGELOG.md` 含 `## [Unreleased]` 區段。`R-04` MUST 仍要求
`# Changelog` 標頭並驗證 Keep-a-Changelog 的 dated 版本段格式。豁免仍為 `policy-exempt:changelog-format`。

#### Scenario: 無 [Unreleased] 但格式合法
- **WHEN** `CHANGELOG.md` 含 `# Changelog` 與合法的 `## [X.Y.Z] - <date>` dated 段、但無 `## [Unreleased]`
- **THEN** R-04 回報 PASS

#### Scenario: 缺 Changelog 標頭
- **WHEN** `CHANGELOG.md` 缺 `# Changelog` 標頭
- **THEN** R-04 回報 FAIL

### Requirement: collate 工具把 fragment 收斂成 Keep-a-Changelog dated 段

`policy_check.changelog` SHALL 提供 `collate --version <X.Y.Z> --date <YYYY-MM-DD>` 子命令，
讀取 `changelog.d/*.md`、依固定 type→段映射分組（`feat`→Added、`fix`→Fixed、
`refactor`/`perf`/`change`→Changed、`remove`→Removed、`deprecate`→Deprecated、`security`→Security），
段順序固定為 Added→Changed→Deprecated→Removed→Fixed→Security，於 `CHANGELOG.md` 插入
`## [X.Y.Z] - <date>` 段後刪除所有 fragment 檔。未知 `type` MUST 回報錯誤而不靜默吞。

#### Scenario: 多 fragment 依 type 分組產段
- **WHEN** `changelog.d/` 含 `type: feat` 與 `type: fix` 兩個 fragment，執行 collate
- **THEN** `CHANGELOG.md` 新增 `## [X.Y.Z] - <date>` 段，feat 進 `### Added`、fix 進 `### Fixed`，且 `changelog.d/` 內 fragment 被刪除

#### Scenario: 未知 type 收斂失敗
- **WHEN** 某 fragment 宣告映射表未涵蓋的 `type`
- **THEN** collate 回報錯誤，不產出該段、不靜默忽略

#### Scenario: 收斂後產出符合 Keep-a-Changelog
- **WHEN** collate 完成
- **THEN** 產出的 dated 段為合法 Keep-a-Changelog 格式，使 R-04 仍通過
