<!-- managed-by: hamanpaul/paulsha-conventions@v1.0.1 -->
<!-- 若修改此檔，同步更新 CLAUDE.md / AGENTS.md / GEMINI.md / .github/copilot-instructions.md 四份 -->
policy_version: 1.0.1

# Agent Policy Checklist

本 repo 受 hamanpaul project policy v1.0.1 管轄。
所有 agent 進入 session 時，必須依下列 checklist 行動。

## 本 repo 的 profile
- policy_profile: `flat` （見 `.paul-project.yml`）
- policy_version: `1.0.1`

## 動工前
- [ ] 確認當前分支不是 `main`
  - 若在 `main`，先開 `feature/<slug>` 分支
  - 若在 `feature/*`，可直接工作，或再開 `wt/<feature>/<subtask>`
- [ ] 若本任務跨多個子項，先建議用 `git worktree` 拆開
- [ ] 若本任務對應某 issue（軟性建議，不打斷流程）：用 `gh issue view <N>` 核對該 issue 與本任務相關，分支可命名為 `feature/<N>-<slug>`，開 PR 時於 body 寫 `Closes #N`
  - 查無對應 issue：照常往下做，不需另開 issue、不需停下

## 改 code 時
- [ ] 同一 PR 必須同步更新 `CHANGELOG.md [Unreleased]`
- [ ] 除非可明確標示為 docs-only / test-only / chore，否則不得省略 CHANGELOG
- [ ] code_paths 涵蓋的檔案變動皆視為 code change
- [ ] 評估 `README.md` / `docs/**` 是否需隨本 PR 同步（R-18；行為或介面有變動務必更新，純內部變動可上 `policy-exempt:docs-sync`）

## 改版號時（release 觸發時）
- [ ] 嚴格遵循 `<MAJOR>.<MINOR>.<PATCH>[-fix.N]`
- [ ] PATCH bump 對應 profile：
  - `stage-driven`: 一個 stage 落地
  - `flat`: 一個 feature batch 完成
- [ ] MINOR bump 需滿足：feature 群組全 landed + 7 天無 hotfix
- [ ] MAJOR bump 需使用者明確核可

## 完成任務（claim done）前
- [ ] `CHANGELOG.md [Unreleased]` 有對應 entry（或 PR 標 `skip-changelog` + 理由）
- [ ] `VERSION` 內容與意圖一致（release label PR 才可偏離 latest tag）
- [ ] `.github/pull_request_template.md` checklist 全勾
- [ ] 測試全綠（本 repo: `python3 -m pytest -q`）
- [ ] `python3 -m policy_check --repo .` 無任何 failure
- [ ] R-17：PR body 若引用 issue（`#N`），必須是 closing-keyword 形式（`Closes/Fixes/Resolves #N`）；只引用不關閉時上 `policy-exempt:issue-link`
- [ ] R-18：code 有變動時已評估並（如需要）同步 `README.md` / `docs/**`，或上 `policy-exempt:docs-sync`
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
- 修改本檔而不同步其他三份 agent convention 檔

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
- `skip-changelog` — R-09 code 變動要求 CHANGELOG entry（特殊用途，需附理由）
- `wip` — R-11 自動通過 PR body checkbox 未全勾（work in progress）
