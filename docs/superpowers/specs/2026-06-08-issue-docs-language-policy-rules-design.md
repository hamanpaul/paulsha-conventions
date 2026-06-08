# 設計：PR↔issue 連結、docs 對齊、repo 語言三條 policy 規則

> 日期：2026-06-08
> 狀態：approved（使用者已逐項拍板）
> 範圍：`paulsha-conventions`（policy 引擎）＋ `hamanpaul/.github`（account-level PR 模板）

## 1. 背景與目標

`paulsha-conventions` 同時維護兩層：

1. **Agent checklist**：四份內容一致的 convention 檔
   （`CLAUDE.md` / `AGENTS.md` / `GEMINI.md` / `.github/copilot-instructions.md`）。
2. **policy_check 引擎**：`R-01`~`R-16` 的 Python 規則 + 測試 + CI gate，repo 自身 dog-food。

使用者要新增三條規則並列入 policy：

1. **PR↔issue 連結**：PR 若對應某 issue，需在 PR 註明；merge 時關閉該 issue，並於 issue 留下「fixed by 該 PR」的關聯。
2. **repo 語言**：repo 屬 `hamanpaul` 或 `paulc-arc` → 所有 comment/PR 內容用 zh-tw；屬 arcadyan GitLab → 用 en_US。
3. **docs 對齊**：現行規則沒有「README 等文件需隨 PR 修改對齊」的要求（R-02 只查段落存在、R-16 只同步 CLI help marker、R-09 只管 CHANGELOG），補上此 gap。

## 2. 落點決策（hybrid）

| # | 規則 | 落點 | 形式 | 豁免 label |
|---|------|------|------|-----------|
| 1 | PR↔issue | 引擎 **R-17** + checklist | FAIL gate：PR body 出現 `#N` → 必須是 closing-keyword（`Closes/Fixes/Resolves #N`）。沒 `#N` → PASS | `policy-exempt:issue-link` |
| 2 | repo 語言 | **checklist-only** | 依 `git remote` 判斷來源套用語言；不做引擎規則（語言偵測不可靠） | —（無引擎規則） |
| 3 | docs 對齊 | 引擎 **R-18** + checklist | **WARN**（過渡期、不擋 merge）：`code_paths` 有變動但 `README.md`/`docs/**` 未動 → WARN | `policy-exempt:docs-sync` |

### 2.1 為何 R-17 只驗「presence/format」而非「relevance」
「PR 對應的是不是正確 issue」是語意判斷，靜態引擎做不到，也符合母辦法 AI-SEC-001 的 human-in-the-loop 原則。
- **relevance**：動工前由人確認（軟性 checklist，見 §3.1）。
- **presence/format**：PR 階段由 R-17 deterministically gate。
- **merge 關 issue + issue 留 cross-reference**：GitHub 原生行為（closing-keyword 進 default branch 自動觸發），引擎不重做。

### 2.2 為何 R-18 採 WARN
`base.py` 的 `Status.WARN` 註解即「未來 MINOR 新 rule 的過渡期」。新規則先 WARN（不擋 merge、只提醒），白名單 label 一併備好，日後可 graduate 成 FAIL。符合「不打斷 workflow」的偏好。

### 2.3 policy_version
`1.0.0 → 1.0.1`（PATCH），讓下游可確認引用的 policy 版本。
- 同步：`.paul-project.yml`、四份 agent 檔的 `policy_version:` 行與 `<!-- managed-by: ...@v1.0.1 -->` 標記、`README.md` 內版本敘述。
- R-14 只要求四份檔與 `.paul-project.yml` 一致，全改 1.0.1 即內部一致。
- `VERSION`（0.0.0 baseline）不動；下游 `hamanpaul/.github` 的 policy_version 不級聯更動。

## 3. 詳細規格

### 3.1 Agent checklist 變更（四份檔內容一致）

- **動工前**（軟性、不打斷）：新增「若任務對應某 issue，建議 `gh issue view <N>` 核對相關性、分支命名帶 id（`feature/<N>-<slug>`），開 PR 時寫 `Closes #N`；查無對應 issue 則照常往下做，不另開 issue、不停下來」。
- **改 code 時**：新增「評估 README/docs 是否需隨本 PR 同步（R-18）」。
- **完成任務前**：新增 R-17（issue 連結格式）、R-18（docs 對齊）、語言規範三項檢查。
- **新增「語言規範」段**：`github.com/hamanpaul/*`、`github.com/paulc-arc/*` → zh-tw；arcadyan GitLab → en_US；涵蓋 PR 標題/內文與所有 comment。依 `git remote -v` 判斷。
- **Exemption Labels 白名單**：新增 `policy-exempt:issue-link`（R-17）、`policy-exempt:docs-sync`（R-18）。
- **policy_version / managed-by 標記**：更新為 1.0.1 / `@v1.0.1`。

### 3.2 引擎 R-17：`policy_check/rules/r17_pr_issue_link.py`

- `rule_id = "R-17"`，`exempt_label = "policy-exempt:issue-link"`。
- 行為：
  - 帶豁免 label → SKIP。
  - `pr_body` 為空 → PASS（非 PR 脈絡，與 R-11 一致）。
  - body 無 `#\d+` bare 參照 → PASS。
  - body 有 bare `#N` 參照，且**存在**至少一個 closing-keyword 參照
    （`(?i)\b(close[sd]?|fix(e[sd])?|resolve[sd]?)\s+#\d+`）→ PASS。
  - body 有 bare `#N` 但**無**任何 closing-keyword 參照 → FAIL（提示加 closing-keyword 或上豁免 label）。
- closing-keyword 採 GitHub 認可集合：close/closes/closed、fix/fixes/fixed、resolve/resolves/resolved。

### 3.3 引擎 R-18：`policy_check/rules/r18_docs_sync.py`

- `rule_id = "R-18"`，`exempt_label = "policy-exempt:docs-sync"`。
- 行為（mirror R-09 偵測，但狀態為 WARN）：
  - 帶豁免 label → SKIP。
  - `code_paths`（來自 config）無命中 `changed_files` → PASS。
  - 有 code 變動，且 `changed_files` 含 `README.md` 或 `docs/` 下任一檔 → PASS。
  - 有 code 變動但無上述 docs 變動 → **WARN**（advisory，不擋 merge）。
- 需確認 CLI/report 將 WARN 視為非失敗（exit 0）；若尚未，調整 exit 邏輯使僅 FAIL 影響 exit code。

### 3.4 README.md

- 標題 `規則總覽（R-01 ~ R-16）` → `~ R-18`。
- 規則表新增兩列：
  - R-17：PR body issue 參照需 closing-keyword 形式｜豁免 `policy-exempt:issue-link`。
  - R-18：code 變動未同步 README/docs（WARN）｜豁免 `policy-exempt:docs-sync`。
- 白名單註記補兩個 label。
- 版本敘述同步 1.0.1。

### 3.5 CHANGELOG.md

`[Unreleased]` 新增條目（R-09 要求）：新增 R-17/R-18、語言 checklist 規範、policy_version 升 1.0.1。

### 3.6 `hamanpaul/.github`（feature 分支 + PR）

在現有 `.github/pull_request_template.md` **追加**（不覆蓋）：

```markdown
## Issue Link
- [ ] 若有對應 issue，已用 `Closes #N`（或 Fixes/Resolves）連結，merge 時自動關閉並於 issue 留 cross-reference；無對應 issue 則免（勾此確認已評估）

## Docs
- [ ] code 變動已評估文件同步：已更新 `README.md`/`docs/**` ／ 無需更新 ／ 已加 `policy-exempt:docs-sync`（擇一）
```

- Summary 段加一條語言確認 checkbox。
- Branch and Policy 段的 exemption 白名單註記補 `policy-exempt:issue-link`、`policy-exempt:docs-sync`。
- 同步該 repo `CHANGELOG.md [Unreleased]`（其 `code_paths` 含 `**/*.md`、`.github/**`，改模板算 code change）。
- 不動該 repo policy_version（維持 1.0.0）。
- 所有 checkbox 採「確認已評估」式語句，確保任何 repo 都能誠實勾選，不破壞 R-11（PR body checkbox 全勾）。

## 4. 驗證

- `python3 -m pytest -q` 全綠（含新 R-17/R-18 測試、既有 self-dogfood R-16 與 action integration）。
- `python3 -m policy_check --repo .` 無 failure（本 repo PR：無 `#N` → R-17 PASS；README 有動 → R-18 PASS；CHANGELOG 有 entry → R-09 PASS；feature 分支 → R-12 PASS）。
- `hamanpaul/.github` PR：`policy_check --repo .` 通過、PR 模板 checkbox 全勾。

## 5. 不做（YAGNI）

- 不對語言做引擎偵測（不可靠）。
- 不加 merge-time 自訂 workflow 去 post「fixed」留言（GitHub 原生 closing-keyword 已涵蓋）。
- 不強制每個 PR 都要有對應 issue。
- 不級聯升 `hamanpaul/.github` 的 policy_version。
- 不改本 repo 的 `VERSION`（仍 0.0.0 baseline）。
