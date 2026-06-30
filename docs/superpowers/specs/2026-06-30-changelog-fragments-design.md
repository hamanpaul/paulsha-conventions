# 設計：#24 CHANGELOG per-PR fragment（消除並行 agent 的 [Unreleased] 衝突）

> 日期：2026-06-30
> 狀態：approved（使用者已逐段拍板）
> 對應 issue：#24（並行 agent 改共用 `[Unreleased]` 頻繁 merge conflict）
> 範圍：`paulsha-conventions` 規則引擎的 CHANGELOG 模型（R-04 / R-09）與 release 收斂工具
> 版本策略：依 `flat` profile 一次 feature batch 一個 PATCH bump（不改版號語意）。

## 1. 背景與目標

本 policy 鼓勵用 `git worktree` 跑並行 agent；多個 PR 同時在共用的
`CHANGELOG.md` `## [Unreleased]` 區段頂端插 bullet，會頻繁 **merge conflict**——
這在本批 #23 / #26 合併時實際發生過（rebase 需手動解 CHANGELOG 衝突）。

業界（**changesets** / **towncrier**）以「每 PR 一個碎片檔」解：作者寫碎片、release 時合併。
本案採此模式，但維持 **agent-first**：agent 寫碎片、gate 驗碎片，不把產出權交給「從 commit 自動生成」的 bot。

**Goals:**
- 讓並行 PR 各自新增獨立 fragment 檔，互不衝突、可獨立 merge。
- 把 `R-09` 從「驗 `[Unreleased]` 有 bullet」改為「驗本 PR 有 fragment」。
- 提供 release 收斂工具，把 fragment 合併成 Keep-a-Changelog dated 段並清空目錄。
- 維持 deterministic、platform-agnostic（純 git-level），與引擎其他規則一致。

**Non-Goals:**
- 不引入 release-please / semantic-release 自動生成。
- 不改版號語意（`flat` profile PATCH 定義不變）。
- 不在本 repo PR 內改 `hamanpaul/new-project-template`（另一個 repo，屬下游 follow-up）。

## 2. 核心決策

### Decision 1 — Hard cutover，行為綁版本，不向下相容
**選擇**：引入版本起**移除 `[Unreleased]` 模型**，待發布記錄一律放 `changelog.d/`。
不做 repo 層 opt-in、不做兩套並存。

**理由**：下游 repo 靠 pin engine 版本（R-23）+ 升版傳播 SOP **主動**升級；未升級的 repo
用舊引擎、舊行為。因此可乾淨切換、不需相容分支，也避免 issue 警告的「兩套 source 並存混淆」。

**替代方案**：repo 層 opt-in（引擎同時支援兩條路）——否決，因增加 R-04/R-09 雙路複雜度，
且使用者明確要求 hard cutover。

### Decision 2 — fragment 位置與檔名：`changelog.d/<issue>-<slug>.md`
**選擇**：towncrier 風格目錄 `changelog.d/`；檔名以 issue 編號開頭 + 短 slug，
例如 `changelog.d/24-changelog-fragments.md`。空目錄以 `.gitkeep` 追蹤。

**理由**：不同 issue 天然不撞名、人能一眼讀懂、與本 repo `openspec/changes` 的 issue-導向命名一致。
同 issue 多 PR 罕見，必要時加 `-2` 後綴。

### Decision 3 — fragment 格式：YAML frontmatter + body
**選擇**：
```markdown
---
type: feat        # 必填，conventional-commit type
scope: changelog  # 選填
issue: 24         # 選填（檔名已含；冗餘但好機器讀）
---
CHANGELOG per-PR fragment：消除並行 agent 的 [Unreleased] 衝突。
```
frontmatter 後的全文 body = CHANGELOG 的一條 bullet。

**理由**：`type` 用 conventional-commit 詞彙與 `R-10` PR title、agent 既有習慣一致；
frontmatter 結構好機器讀，body 自由書寫。

### Decision 4 — type → Keep-a-Changelog 段 固定映射
| type | KaC 段 |
|---|---|
| `feat` | Added |
| `fix` | Fixed |
| `refactor` / `perf` / `change` | Changed |
| `remove` | Removed |
| `deprecate` | Deprecated |
| `security` | Security |

- 段順序固定：**Added → Changed → Deprecated → Removed → Fixed → Security**。
- 未知 type → collate **FAIL**（明確錯誤，不靜默吞）。
- `docs` / `test` / `chore` 不是合法 fragment type；該類 PR 走 `skip-changelog`（沿用現有慣例）。

### Decision 5 — release 收斂工具：`policy_check.changelog` 子命令
**選擇**：新增 `python3 -m policy_check.changelog collate --version X.Y.Z --date YYYY-MM-DD`，
比照 `policy_check.drift`：純邏輯（解析/分組/排序/產段）與 I/O 邊緣（讀目錄、寫檔、刪檔）分離、可單元測試。

**行為**：讀 `changelog.d/*.md` → 解析 frontmatter → 依 type 映射分組、組內保序 → 在 `# Changelog`
之後（最新 dated 段之前）插入 `## [X.Y.Z] - YYYY-MM-DD` 段（KaC 格式）→ 刪除所有 fragment 檔。
無 fragment 時 collate 仍可產出空段或明確提示（實作定）。升版 SOP 多一步「先 collate 再 bump」。

### Decision 6 — 規則行為邊界
- **R-09**（code↔changelog sync）：核心改為「本 PR 的 `changed_files` 是否含 `changelog.d/*.md`」。
  仍受 `code_paths` 觸發、仍可 `skip-changelog` 豁免、仍 advisory 之外的 FAIL 性質不變。
- **R-04**（changelog format）：移除 `## [Unreleased]` 必備要求；保留 `# Changelog` 標頭與
  Keep-a-Changelog dated 段格式驗證。豁免仍 `policy-exempt:changelog-format`。
- **無新增豁免 label**（白名單不變）。

## 3. 元件與資料流

| 元件 | 做什麼 | 輸入 | 輸出 |
|---|---|---|---|
| `changelog.d/<issue>-<slug>.md` | 單一 PR 的待發布記錄 | 作者/agent 撰寫 | 一個 fragment 檔 |
| `R-09` | 驗 code 變動是否附 fragment | `changed_files`, `code_paths` | PASS/FAIL/SKIP |
| `R-04` | 驗 CHANGELOG 結構（不再要求 [Unreleased]） | `CHANGELOG.md` | PASS/FAIL/SKIP |
| `policy_check.changelog collate` | 收斂 fragment → dated 段 + 清空目錄 | `changelog.d/*.md`, version, date | 改寫後的 `CHANGELOG.md` |

並行安全來自：每 PR 只新增**自己的一個檔**，零共用行 → git 永不衝突。

## 4. 測試策略

### 4.1 `policy_check/changelog.py` 純邏輯
- frontmatter 解析（type 必填、缺 type → 錯誤；scope/issue 選填）。
- type → KaC 段映射；未知 type → FAIL。
- 多 fragment 分組、段順序固定、組內保序。
- 產出 KaC 段字串正確（`## [X.Y.Z] - date` + `### <段>` + bullets）。
- collate 後 `changelog.d/` 清空（保留 `.gitkeep`）。

### 4.2 `R-09` 改寫
- code 變動 + 有 `changelog.d/*.md` fragment → PASS。
- code 變動 + 無 fragment → FAIL。
- `skip-changelog` label → SKIP。
- 無 code 變動 → PASS（not applicable）。

### 4.3 `R-04` 改寫
- 無 `## [Unreleased]` 但有 `# Changelog` + 合法 dated 段 → PASS。
- 缺 `# Changelog` → FAIL。
- 既有 dated 段格式驗證不退化。

### 4.4 並行驗收
- 兩個不同 issue 的 fragment（不同檔）可各自獨立存在、互不影響。

## 5. 本 repo dogfood 與文件

- 建 `changelog.d/`（`.gitkeep`），本案 #24 自己用 fragment 記錄。
- 既有 `## [Unreleased]` backlog（多為 1.0.0–1.0.2 未切段的歷史內容）：保留歷史內容、
  移除 `## [Unreleased]` 標頭，不回頭重切舊版段（一次性，實作時收斂）。
- 更新 canonical `CLAUDE.md`（checklist 的 CHANGELOG 段改 fragment 說明；其餘三檔 symlink 自動跟隨）。
- 更新 `README.md`（fragment 模型、`collate` 指令、R-04/R-09 新行為、規則表描述）。

## 6. 相容性與 rollout

- **行為綁版本**：引入此能力為一次 PATCH bump；下游未升級者用舊引擎、舊 `[Unreleased]` 行為。
- 升級到本版的下游 repo，依升版傳播 SOP 採用 fragment 模型（建 `changelog.d/`、移除 `[Unreleased]`）。
- `new-project-template` 骨架同步為**下游 follow-up**，不在本 repo PR 內。

## 7. Open Questions

- 無。關鍵邊界（hard cutover、`changelog.d/<issue>-<slug>.md`、conventional-commit type +
  固定映射、`policy_check.changelog collate`、R-09/R-04 改寫）已於 brainstorm 定稿。
- 實作期可再收斂的小點：既有 [Unreleased] backlog 的一次性處理方式；是否提供 `create`
  fragment helper（傾向 YAGNI 不做）。
