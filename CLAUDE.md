<!-- managed-by: hamanpaul/paulsha-conventions@v1.0.12 -->
<!-- 此為 canonical 真檔；AGENTS.md / GEMINI.md / .github/copilot-instructions.md 為指向本檔的 symlink，只維護本檔 -->
policy_version: 1.0.12

# Agent Policy Checklist

本 repo 受 hamanpaul project policy v1.0.12 管轄。
所有 agent 進入 session 時，必須依下列 checklist 行動。

## 本 repo 的 profile
- policy_profile: `flat` （見 `.paul-project.yml`）
- policy_version: `1.0.12`

## 動工前
- [ ] 確認當前分支不是 `main`
  - 若在 `main`，先開 `feature/<slug>` 分支
  - 若在 `feature/*`，可直接工作，或再開 `wt/<feature>/<subtask>`
- [ ] 若本任務跨多個子項，先建議用 `git worktree` 拆開
- [ ] 若本任務對應某 issue（軟性建議，不打斷流程）：用 `gh issue view <N>` 核對該 issue 與本任務相關，分支可命名為 `feature/<N>-<slug>`，開 PR 時於 body 寫 `Closes #N`
  - 查無對應 issue：照常往下做，不需另開 issue、不需停下

## 改 code 時
- [ ] 同一 PR 必須新增一個 changelog fragment `changelog.d/<issue>-<slug>.md`（frontmatter `type` 必填、`scope`/`issue` 選填；body = 一條描述）
- [ ] 除非可明確標示為 docs-only / test-only / chore，否則不得省略 fragment
- [ ] code_paths 涵蓋的檔案變動皆視為 code change
- [ ] 評估 `README.md` / `docs/**` 是否需隨本 PR 同步（R-18；行為或介面有變動務必更新，純內部變動可上 `policy-exempt:docs-sync`）
- [ ] R-22：搬移／改名／刪除 code 產物（檔案、`def`/`class`）時，同步更新 `README.md` / `docs/**` 中引用它的段落；無法即時處理上 `policy-exempt:doc-reference` 並附理由

## 改版號時（release 觸發時）
- [ ] 嚴格遵循 `<MAJOR>.<MINOR>.<PATCH>[-fix.N]`
- [ ] PATCH bump 對應 profile：
  - `stage-driven`: 一個 stage 落地
  - `flat`: 一個 feature batch 完成
- [ ] MINOR bump 需滿足：feature 群組全 landed + 7 天無 hotfix
- [ ] MAJOR bump 需使用者明確核可
- [ ] 若本 PR 將版本 bump 延後（feature 先進 `[Unreleased]`），merge 當下必須**立即**補做對應 release bump（`VERSION` / `policy_version` / canonical `CLAUDE.md`（其餘三檔 symlink 自動跟隨）/ `managed-by` 標記 / tag / `RELEASES.md`），不得留置

## 完成任務（claim done）前
- [ ] 本 PR 有新增對應的 changelog fragment `changelog.d/<issue>-<slug>.md`（或 PR 標 `skip-changelog` + 理由）
- [ ] `VERSION` 內容與意圖一致（release label PR 才可偏離 latest tag）
- [ ] `.github/pull_request_template.md` checklist 全勾
- [ ] 測試全綠（本 repo: `python3 -m pytest -q`）
- [ ] `python3 -m policy_check --repo .` 無任何 failure
- [ ] R-17：PR body 若引用 issue（`#N`），必須是 closing-keyword 形式（`Closes/Fixes/Resolves #N`）；只引用不關閉時上 `policy-exempt:issue-link`
- [ ] R-18：code 有變動時已評估並（如需要）同步 `README.md` / `docs/**`，或上 `policy-exempt:docs-sync`
- [ ] R-19：repo 有 `tests/` 時，CI workflow 有實際執行測試（pytest 等）；新增測試套件而 CI 未涵蓋時同步補上
- [ ] R-21：宣告 `tier: shareable` 的 repo 不得含雇主機敏標記（內部代號、裝置型號等）、個人絕對路徑或憑證模式；合法引用上 `secret_scan.allow` 或命中時上 `policy-exempt:secret-scan` 並附理由
- [ ] R-22：docs 對本次刪改 code 產物的引用無懸空（CI 報「本次新破壞」FAIL、陳年 WARN），或上 `policy-exempt:doc-reference`
- [ ] R-23：workflow 對引擎的 pin 版本與 `policy_version` 一致（tag `@vX.Y.Z`，或 SHA `@<sha>` + 尾註 `# vX.Y.Z`），或上 `policy-exempt:engine-pin`（`./` 在地引用或未設 `conventions_engine.repo` 時不適用）
- [ ] R-24：repo 宣告 `moc` 時，本次變更已同步靜態脈絡（`moc.static`）與動態地圖（`moc.map` 無懸空、新產物已連結），或上 `policy-exempt:moc-alignment`（未宣告 `moc` 時不適用）
- [ ] 語言：PR 標題／內文與所有 comment 的語言符合本 repo 規範（見「語言規範」段）
- [ ] 若跳過任何檢查，PR 必須帶對應豁免 label + 理由

## 語言規範（PR / comment）
依 repo 來源決定撰寫語言（用 `git remote -v` 判斷）：
- `github.com/hamanpaul/*`、`github.com/paulc-arc/*` → 一律 **zh-tw**
- arcadyan GitLab → 一律 **en_US**

涵蓋範圍：PR 標題、PR 內文、code review 與 issue 的所有 comment。本 repo 屬 `hamanpaul` → zh-tw。

## 禁止
- 直接 commit 到 `main`
- 建立不符合命名規則的分支（必須 `feature/<slug>` 或 `wt/<feature>/<subtask>`）
- 發明新 `policy-exempt:*` label（**只能用 policy 列舉的白名單**）
- 把 agent symlink（AGENTS.md / GEMINI.md / .github/copilot-instructions.md）還原成獨立複本（`agent_files.mode: symlink` 下 R-14 會 FAIL）

## Exemption Labels 白名單
僅允許使用以下 labels 豁免對應規則（其他一律視同未豁免）：
- `policy-exempt:readme-sections` — R-02 README 必備段落
- `policy-exempt:changelog-format` — R-04 CHANGELOG 格式
- `policy-exempt:pr-title` — R-10 PR title conventional-commit 格式
- `policy-exempt:branch-name` — R-12 分支來源規則
- `policy-exempt:agent-files` — R-13 agent convention files 存在
- `policy-exempt:cli-help` — R-16 CLI help 同步
- `policy-exempt:issue-link` — R-17 PR body issue 參照需 closing-keyword 形式
- `policy-exempt:docs-sync` — R-18 code 變動需同步 README/docs
- `policy-exempt:ci-tests` — R-19 repo 有測試則 CI 必須執行
- `policy-exempt:secret-scan` — R-21 機密掃描（tier=shareable 命中雇主標記）
- `policy-exempt:doc-reference` — R-22 文件懸空引用（doc dangling reference）
- `policy-exempt:engine-pin` — R-23 引擎 pin 版本與 policy_version 對齊
- `policy-exempt:moc-alignment` — R-24 MOC 與本次變更對齊
- `skip-changelog` — R-09 code 變動要求 CHANGELOG entry（特殊用途，需附理由）
- `wip` — R-11 自動通過 PR body checkbox 未全勾（work in progress）

## Doc-alignment review（PR review 時）
review 變更時，除了 R-22 抓得到的懸空引用，另留意**語意陳舊**：引用都還在、但 docs 描述了已被這次變更改掉的架構／行為；發現時於 PR 留言指出、建議作者更新。Advisory，不擋 merge。建議將 GitHub Copilot 設為 PR reviewer 以啟用此層。

MOC 的**狀態語意對齊**（`moc.map` 上某 stage 宣稱 done 是否真 done、被 postpone 的 stage 是否還誤掛 done）同屬此 advisory 層：R-24 只確定性檢查連結懸空／孤兒與靜態鮮度，狀態是否真對齊由 Copilot reviewer 留言提醒。
