# Three-Repo Rollout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `hamanpaul/.github` and `hamanpaul/new-project-template`, wire them to `hamanpaul/paulsha-conventions`, and validate the rollout with a smoke-test repository.

**Architecture:** Keep all rule logic and reusable workflow code inside `hamanpaul/paulsha-conventions`. Use `hamanpaul/.github` only for account-level community health defaults, and use `hamanpaul/new-project-template` only for bootstrap files that point back to the central policy engine by pinned commit SHA.

**Tech Stack:** GitHub repositories, Markdown, YAML, GitHub Actions, `gh` CLI, `policy_check` CLI, Python virtual environments

---

## Workspace layout

- Current policy engine repo: `/home/paul_chen/prj_pri/paulsha-conventions`
- Account defaults repo clone target: `/home/paul_chen/prj_pri/.github`
- Template repo clone target: `/home/paul_chen/prj_pri/new-project-template`
- Smoke-test repo clone target: `/home/paul_chen/prj_pri/new-project-template-smoke`
- Shared validation virtualenv: `/tmp/paulsha-policy-venv`
- Frozen policy reference for downstream repos: `dbde416e3595593645799970bd3f9ad3bb05cfe9`

## Shared setup

- [ ] **Step 1: Create the shared validation virtualenv**

```bash
python3 -m venv /tmp/paulsha-policy-venv
/tmp/paulsha-policy-venv/bin/pip install -q PyYAML pytest
/tmp/paulsha-policy-venv/bin/pip install -q -e /home/paul_chen/prj_pri/paulsha-conventions --no-deps
```

- [ ] **Step 2: Verify the policy engine repo is a good downstream source**

```bash
/tmp/paulsha-policy-venv/bin/python -m policy_check --repo /home/paul_chen/prj_pri/paulsha-conventions
/tmp/paulsha-policy-venv/bin/pytest -q /home/paul_chen/prj_pri/paulsha-conventions/tests
```

Expected:

```text
policy_check: 16 pass / 0 fail
pytest: all tests pass
```

### Task 1: Create and merge `hamanpaul/.github`

**Files:**
- Create: `/home/paul_chen/prj_pri/.github/.paul-project.yml`
- Create: `/home/paul_chen/prj_pri/.github/README.md`
- Create: `/home/paul_chen/prj_pri/.github/CHANGELOG.md`
- Create: `/home/paul_chen/prj_pri/.github/VERSION`
- Create: `/home/paul_chen/prj_pri/.github/AGENTS.md`
- Create: `/home/paul_chen/prj_pri/.github/CLAUDE.md`
- Create: `/home/paul_chen/prj_pri/.github/GEMINI.md`
- Create: `/home/paul_chen/prj_pri/.github/.github/copilot-instructions.md`
- Create: `/home/paul_chen/prj_pri/.github/.github/pull_request_template.md`
- Create: `/home/paul_chen/prj_pri/.github/CONTRIBUTING.md`
- Create: `/home/paul_chen/prj_pri/.github/SECURITY.md`

- [ ] **Step 1: Create the repository and branch**

```bash
cd /home/paul_chen/prj_pri
gh repo create hamanpaul/.github \
  --public \
  --clone \
  --add-readme \
  --description "Account-wide community health defaults for hamanpaul repositories"
cd /home/paul_chen/prj_pri/.github
git checkout -b feature/bootstrap-account-defaults
```

- [ ] **Step 2: Run `policy_check` before adding the bootstrap files**

```bash
/tmp/paulsha-policy-venv/bin/python -m policy_check --repo /home/paul_chen/prj_pri/.github
```

Expected:

```text
FAIL: missing CHANGELOG.md, VERSION, .paul-project.yml, and agent convention files
```

- [ ] **Step 3: Write the root metadata files**

```bash
cat > /home/paul_chen/prj_pri/.github/.paul-project.yml <<'EOF'
policy_profile: flat
policy_version: 1.0.0
code_paths:
  - "**/*.md"
  - "**/*.yml"
  - "**/*.yaml"
  - ".github/**"
EOF

cat > /home/paul_chen/prj_pri/.github/README.md <<'EOF'
# .github

Default community health files for repositories owned by `hamanpaul`.

## Install

No install step is required. GitHub reads this public `.github` repository automatically when another `hamanpaul/*` repository does not provide its own supported community health file.

## Usage

Use this repository to keep account-level defaults such as `CONTRIBUTING.md`, `SECURITY.md`, and the default pull request template in one place. Rule logic and automation stay in `hamanpaul/paulsha-conventions`.

## Version

`VERSION` tracks the revision of these account-level defaults. Update it together with `CHANGELOG.md` when the defaults change.
EOF

cat > /home/paul_chen/prj_pri/.github/CHANGELOG.md <<'EOF'
# Changelog

本專案所有重大變更都會記錄在此檔案。

格式基於 [Keep a Changelog 1.1.0](https://keepachangelog.com/zh-TW/1.1.0/)，
本專案遵循 hamanpaul project policy v1.0.0。

## [Unreleased]

### Added
- 建立 `hamanpaul/.github` account-level community health defaults repo

### Changed
- 無

### Fixed
- 無
EOF

printf '0.0.0\n' > /home/paul_chen/prj_pri/.github/VERSION
```

- [ ] **Step 4: Write one agent convention file and copy it to the other three paths**

```bash
mkdir -p /home/paul_chen/prj_pri/.github/.github

cat > /home/paul_chen/prj_pri/.github/AGENTS.md <<'EOF'
<!-- managed-by: hamanpaul/paulsha-conventions@v1.0.0 -->
<!-- 若修改此檔，同步更新 CLAUDE.md / AGENTS.md / GEMINI.md / .github/copilot-instructions.md 四份 -->
policy_version: 1.0.0

# Agent Policy Checklist

本 repo 受 hamanpaul project policy v1.0.0 管轄。
所有 agent 進入 session 時，必須依下列 checklist 行動。

## 本 repo 的 profile
- policy_profile: `flat` （見 `.paul-project.yml`）
- policy_version: `1.0.0`

## 動工前
- [ ] 確認當前分支不是 `main`
  - 若在 `main`，先開 `feature/<slug>` 分支
  - 若在 `feature/*`，可直接工作，或再開 `wt/<feature>/<subtask>`
- [ ] 若本任務跨多個子項，先建議用 `git worktree` 拆開

## 改 code 時
- [ ] 同一 PR 必須同步更新 `CHANGELOG.md [Unreleased]`
- [ ] 除非可明確標示為 docs-only / test-only / chore，否則不得省略 CHANGELOG
- [ ] code_paths 涵蓋的檔案變動皆視為 code change

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
- [ ] `python3 -m policy_check --repo .` 無任何 failure
- [ ] 若本 repo 有額外測試 / lint / build 指令，需一併通過
- [ ] 若跳過任何檢查，PR 必須帶對應豁免 label + 理由

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
- `skip-changelog` — R-09 code 變動要求 CHANGELOG entry（特殊用途，需附理由）
- `wip` — R-11 自動通過 PR body checkbox 未全勾（work in progress）
EOF

cp /home/paul_chen/prj_pri/.github/AGENTS.md /home/paul_chen/prj_pri/.github/CLAUDE.md
cp /home/paul_chen/prj_pri/.github/AGENTS.md /home/paul_chen/prj_pri/.github/GEMINI.md
cp /home/paul_chen/prj_pri/.github/AGENTS.md /home/paul_chen/prj_pri/.github/.github/copilot-instructions.md
```

- [ ] **Step 5: Add the account-level default files**

```bash
cat > /home/paul_chen/prj_pri/.github/.github/pull_request_template.md <<'EOF'
## Summary
- [ ] 說明本 PR 做了什麼
- [ ] 說明為什麼需要這個變更

## Changelog
- [ ] 已更新 `CHANGELOG.md [Unreleased]`
- [ ] 本 PR 屬於 docs-only / test-only / chore，無需 CHANGELOG
- [ ] 需使用 `skip-changelog`，原因已填在下方 Notes

## Validation
- [ ] `python3 -m policy_check --repo .` 已通過
- [ ] 本 repo 額外的 test / lint / build 已通過，或本 PR 無相關指令

## Branch and Policy
- [ ] 來源分支符合 policy（`feature/*` 或 `wt/<feature>/*`）
- [ ] 未直接 push 到 `main`
- [ ] 未新增未列入白名單的 exemption label

## Notes
- 無 / 補充如下
EOF

cat > /home/paul_chen/prj_pri/.github/CONTRIBUTING.md <<'EOF'
# Contributing

Thanks for contributing to repositories under `hamanpaul`.

## Branch flow

1. Do not work directly on `main`.
2. Start from `feature/<slug>`.
3. If a feature splits into sub-work, branch from the parent feature branch with `wt/<feature>/<subtask>`.
4. Open a pull request back to `main` or back to the parent `feature/*` branch.

## Required checks

- Keep `README.md`, `CHANGELOG.md`, `VERSION`, and `.paul-project.yml` aligned.
- Run `python3 -m policy_check --repo .` before opening the pull request.
- If the repository defines extra test, lint, or build commands, run them too.
- Use only the white-listed exemption labels from the policy.

## Changelog rule

If a change touches files covered by `code_paths`, update `CHANGELOG.md [Unreleased]` in the same pull request unless the change is clearly docs-only, test-only, or chore-only, or the pull request uses `skip-changelog` with a written reason.

## Workflow references

When a repository calls this shared policy workflow path, pin both the reusable workflow ref and `policy_engine_ref` to the same full 40-character commit SHA. Do not use tags, short SHAs, or branch refs such as `@main`.
EOF

cat > /home/paul_chen/prj_pri/.github/SECURITY.md <<'EOF'
# Security Policy

## Reporting a Vulnerability

Do not open a public issue for a suspected security problem.

1. If GitHub private vulnerability reporting is enabled for the affected repository, use the **Report a vulnerability** button.
2. If private vulnerability reporting is not enabled, contact the repository owner through the contact address listed on their GitHub profile.
3. Include the affected repository, the exact commit or tag, reproduction steps, and the impact you observed.

## Response Expectations

The initial goal is to confirm receipt, reproduce the issue, and decide whether mitigation or a private fix branch is needed before public disclosure.
EOF
```

- [ ] **Step 6: Run the validation command until it passes**

```bash
/tmp/paulsha-policy-venv/bin/python -m policy_check --repo /home/paul_chen/prj_pri/.github
```

Expected:

```text
16 pass / 0 fail
```

- [ ] **Step 7: Commit, push, open a PR, and merge it**

```bash
cd /home/paul_chen/prj_pri/.github
git add .
git commit -m "docs(defaults): 建立 account-level community health defaults" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push -u origin feature/bootstrap-account-defaults
gh pr create \
  --base main \
  --head feature/bootstrap-account-defaults \
  --title "docs(defaults): 建立 account-level community health defaults" \
  --body $'## Summary\n- [x] 說明本 PR 做了什麼\n- [x] 說明為什麼需要這個變更\n\n## Changelog\n- [x] 已更新 `CHANGELOG.md [Unreleased]`\n- [ ] 本 PR 屬於 docs-only / test-only / chore，無需 CHANGELOG\n- [ ] 需使用 `skip-changelog`，原因已填在下方 Notes\n\n## Validation\n- [x] `python3 -m policy_check --repo .` 已通過\n- [x] 本 repo 額外的 test / lint / build 已通過，或本 PR 無相關指令\n\n## Branch and Policy\n- [x] 來源分支符合 policy（`feature/*` 或 `wt/<feature>/*`）\n- [x] 未直接 push 到 `main`\n- [x] 未新增未列入白名單的 exemption label\n\n## Notes\n- 無\n'
gh pr merge --squash --delete-branch
```

### Task 2: Create and merge `hamanpaul/new-project-template`

**Files:**
- Create: `/home/paul_chen/prj_pri/new-project-template/.paul-project.yml`
- Create: `/home/paul_chen/prj_pri/new-project-template/README.md`
- Create: `/home/paul_chen/prj_pri/new-project-template/CHANGELOG.md`
- Create: `/home/paul_chen/prj_pri/new-project-template/VERSION`
- Create: `/home/paul_chen/prj_pri/new-project-template/AGENTS.md`
- Create: `/home/paul_chen/prj_pri/new-project-template/CLAUDE.md`
- Create: `/home/paul_chen/prj_pri/new-project-template/GEMINI.md`
- Create: `/home/paul_chen/prj_pri/new-project-template/.github/copilot-instructions.md`
- Create: `/home/paul_chen/prj_pri/new-project-template/.github/workflows/policy-check.yml`

- [ ] **Step 1: Create the template repository and branch**

```bash
cd /home/paul_chen/prj_pri
gh repo create hamanpaul/new-project-template \
  --public \
  --clone \
  --add-readme \
  --description "Starter skeleton for repositories that follow hamanpaul/paulsha-conventions"
cd /home/paul_chen/prj_pri/new-project-template
git checkout -b feature/bootstrap-new-project-template
```

- [ ] **Step 2: Run `policy_check` before adding the scaffold**

```bash
/tmp/paulsha-policy-venv/bin/python -m policy_check --repo /home/paul_chen/prj_pri/new-project-template
```

Expected:

```text
FAIL: missing CHANGELOG.md, VERSION, .paul-project.yml, and agent convention files
```

- [ ] **Step 3: Write the root scaffold files**

```bash
mkdir -p /home/paul_chen/prj_pri/new-project-template/.github/workflows

cat > /home/paul_chen/prj_pri/new-project-template/.paul-project.yml <<'EOF'
policy_profile: flat
policy_version: 1.0.0
code_paths:
  - "**/*.md"
  - "**/*.yml"
  - "**/*.yaml"
  - "**/*.py"
  - "**/*.sh"
  - "scripts/**"
EOF

cat > /home/paul_chen/prj_pri/new-project-template/README.md <<'EOF'
# Project Template

> GitHub template skeleton for repositories that follow `hamanpaul/paulsha-conventions`. Replace the title and summary after generating a new repository.

## Install

Document local setup here. If the generated repository does not have runtime dependencies yet, explain only the bootstrap steps.

## Usage

Document the common developer workflow here. At minimum, run `python3 -m policy_check --repo .` before opening a pull request.

## Version

`VERSION` is the single source of truth for the repository version. Update it together with `CHANGELOG.md` according to the selected `policy_profile`.
EOF

cat > /home/paul_chen/prj_pri/new-project-template/CHANGELOG.md <<'EOF'
# Changelog

本專案所有重大變更都會記錄在此檔案。

格式基於 [Keep a Changelog 1.1.0](https://keepachangelog.com/zh-TW/1.1.0/)，
本專案遵循 hamanpaul project policy v1.0.0。

## [Unreleased]

### Added
- 建立 `hamanpaul/new-project-template` 新專案骨架

### Changed
- 無

### Fixed
- 無
EOF

printf '0.0.0\n' > /home/paul_chen/prj_pri/new-project-template/VERSION

cat > /home/paul_chen/prj_pri/new-project-template/.github/workflows/policy-check.yml <<'EOF'
name: Policy Check

on:
  pull_request:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  policy:
    uses: hamanpaul/paulsha-conventions/.github/workflows/reusable-policy-check.yml@dbde416e3595593645799970bd3f9ad3bb05cfe9
    with:
      policy_profile: flat
      policy_version: "1.0.0"
EOF
```

- [ ] **Step 4: Reuse the generic agent convention file in all four locations**

```bash
cp /home/paul_chen/prj_pri/.github/AGENTS.md /home/paul_chen/prj_pri/new-project-template/AGENTS.md
cp /home/paul_chen/prj_pri/.github/AGENTS.md /home/paul_chen/prj_pri/new-project-template/CLAUDE.md
cp /home/paul_chen/prj_pri/.github/AGENTS.md /home/paul_chen/prj_pri/new-project-template/GEMINI.md
cp /home/paul_chen/prj_pri/.github/AGENTS.md /home/paul_chen/prj_pri/new-project-template/.github/copilot-instructions.md
```

- [ ] **Step 5: Validate the template repo and mark it as a template**

```bash
/tmp/paulsha-policy-venv/bin/python -m policy_check --repo /home/paul_chen/prj_pri/new-project-template
cd /home/paul_chen/prj_pri/new-project-template
gh repo edit hamanpaul/new-project-template --template
```

Expected:

```text
policy_check: 16 pass / 0 fail
gh repo edit: template flag enabled
```

- [ ] **Step 6: Commit, push, open a PR, and merge it**

```bash
cd /home/paul_chen/prj_pri/new-project-template
git add .
git commit -m "docs(template): 建立新專案骨架" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push -u origin feature/bootstrap-new-project-template
gh pr create \
  --base main \
  --head feature/bootstrap-new-project-template \
  --title "docs(template): 建立新專案骨架" \
  --body $'## Summary\n- [x] 說明本 PR 做了什麼\n- [x] 說明為什麼需要這個變更\n\n## Changelog\n- [x] 已更新 `CHANGELOG.md [Unreleased]`\n- [ ] 本 PR 屬於 docs-only / test-only / chore，無需 CHANGELOG\n- [ ] 需使用 `skip-changelog`，原因已填在下方 Notes\n\n## Validation\n- [x] `python3 -m policy_check --repo .` 已通過\n- [x] 本 repo 額外的 test / lint / build 已通過，或本 PR 無相關指令\n\n## Branch and Policy\n- [x] 來源分支符合 policy（`feature/*` 或 `wt/<feature>/*`）\n- [x] 未直接 push 到 `main`\n- [x] 未新增未列入白名單的 exemption label\n\n## Notes\n- 無\n'
gh pr merge --squash --delete-branch
```

### Task 3: Smoke-test the template and `.github` defaults together

**Files:**
- Create: `/home/paul_chen/prj_pri/new-project-template-smoke/README.md`
- Modify: `/home/paul_chen/prj_pri/new-project-template-smoke/CHANGELOG.md`
- Test: `gh api repos/hamanpaul/new-project-template-smoke/community/profile`
- Test: `gh run list -R hamanpaul/new-project-template-smoke --workflow "Policy Check"`

- [ ] **Step 1: Generate a smoke-test repo from the template**

```bash
cd /home/paul_chen/prj_pri
gh repo create hamanpaul/new-project-template-smoke \
  --private \
  --template hamanpaul/new-project-template \
  --clone \
  --description "Smoke test for new-project-template"
cd /home/paul_chen/prj_pri/new-project-template-smoke
git checkout -b feature/template-smoke
```

- [ ] **Step 2: Replace the template summary with smoke-test metadata**

```bash
cat > /home/paul_chen/prj_pri/new-project-template-smoke/README.md <<'EOF'
# new-project-template-smoke

> Smoke-test repository generated from `hamanpaul/new-project-template`.

## Install

No project-specific install steps are needed for this smoke test. The only required command is the policy validation step.

## Usage

Run `python3 -m policy_check --repo .` locally before opening the pull request, then confirm the `Policy Check` workflow passes in GitHub Actions.

## Version

`VERSION` remains the single source of truth for repository versioning during the smoke test.
EOF

python3 - <<'PY'
from pathlib import Path
path = Path("/home/paul_chen/prj_pri/new-project-template-smoke/CHANGELOG.md")
text = path.read_text()
marker = "### Changed\n- 無\n"
replacement = "### Changed\n- 將 template README 內容替換為 smoke-test 專案描述\n"
if marker not in text:
    raise SystemExit("Expected CHANGELOG marker not found")
path.write_text(text.replace(marker, replacement, 1))
PY
```

- [ ] **Step 3: Run the local policy validation**

```bash
/tmp/paulsha-policy-venv/bin/python -m policy_check --repo /home/paul_chen/prj_pri/new-project-template-smoke
```

Expected:

```text
16 pass / 0 fail
```

- [ ] **Step 4: Commit and push the smoke-test branch**

```bash
cd /home/paul_chen/prj_pri/new-project-template-smoke
git add README.md CHANGELOG.md
git commit -m "docs: 驗證 template smoke repo" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push -u origin feature/template-smoke
```

- [ ] **Step 5: Verify the default PR template is loaded from `hamanpaul/.github`**

```bash
cd /home/paul_chen/prj_pri/new-project-template-smoke
gh pr create --web --base main --head feature/template-smoke
```

Expected:

```text
The browser opens a new PR form whose body is prefilled from hamanpaul/.github/.github/pull_request_template.md.
```

- [ ] **Step 6: Verify the account-level `CONTRIBUTING.md` and `SECURITY.md` files are visible through the community profile API**

```bash
gh api repos/hamanpaul/new-project-template-smoke/community/profile | jq '{contributing: (.files.contributing != null), security: (.files.security != null)}'
```

Expected:

```json
{
  "contributing": true,
  "security": true
}
```

- [ ] **Step 7: Wait for the smoke-test workflow to pass**

```bash
gh run list -R hamanpaul/new-project-template-smoke --workflow "Policy Check" --limit 1
```

Expected:

```text
The newest run for workflow "Policy Check" is completed with conclusion "success".
```

- [ ] **Step 8: Delete the smoke-test repo after validation**

```bash
gh repo delete hamanpaul/new-project-template-smoke --yes
rm -rf /home/paul_chen/prj_pri/new-project-template-smoke
```

### Task 4: Record the rollout result back in `paulsha-conventions`

**Files:**
- Modify: `/home/paul_chen/prj_pri/paulsha-conventions/CHANGELOG.md`
- Modify: `/home/paul_chen/prj_pri/paulsha-conventions/README.md`

- [ ] **Step 1: Create the documentation branch in `paulsha-conventions`**

```bash
cd /home/paul_chen/prj_pri/paulsha-conventions
git checkout -b feature/update-readme-after-rollout
```

- [ ] **Step 2: Insert the rollout note into `CHANGELOG.md [Unreleased]`**

```bash
python3 - <<'PY'
from pathlib import Path
path = Path("/home/paul_chen/prj_pri/paulsha-conventions/CHANGELOG.md")
text = path.read_text()
marker = "### Added\n"
insert = "### Added\n- 建立三 repo 生態的 rollout artifact：`hamanpaul/.github` 與 `hamanpaul/new-project-template`\n"
if marker not in text:
    raise SystemExit("Expected CHANGELOG marker not found")
path.write_text(text.replace(marker, insert, 1))
PY
```

- [ ] **Step 3: Replace planned repo names in `README.md` with live links**

```bash
python3 - <<'PY'
from pathlib import Path
path = Path("/home/paul_chen/prj_pri/paulsha-conventions/README.md")
text = path.read_text()
old = "## 相關專案\n\n- [`hamanpaul/.github`](https://github.com/hamanpaul/.github)：GitHub 社群預設（PR template / Issue template / SECURITY / CONTRIBUTING）\n- [`hamanpaul/new-project-template`](https://github.com/hamanpaul/new-project-template)：新專案骨架（供 `gh repo create --template` 使用）\n"
new = "## 相關專案\n\n- [`hamanpaul/.github`](https://github.com/hamanpaul/.github)：account-level GitHub community health defaults\n- [`hamanpaul/new-project-template`](https://github.com/hamanpaul/new-project-template)：新專案骨架（供 `gh repo create --template` 使用）\n"
if old not in text:
    raise SystemExit("Expected README block not found")
path.write_text(text.replace(old, new, 1))
PY
```

- [ ] **Step 4: Validate the policy engine repo again**

```bash
/tmp/paulsha-policy-venv/bin/python -m policy_check --repo /home/paul_chen/prj_pri/paulsha-conventions
/tmp/paulsha-policy-venv/bin/pytest -q /home/paul_chen/prj_pri/paulsha-conventions/tests
```

Expected:

```text
policy_check: 16 pass / 0 fail
pytest: all tests pass
```

- [ ] **Step 5: Commit the documentation update in `paulsha-conventions`**

```bash
cd /home/paul_chen/prj_pri/paulsha-conventions
git add README.md CHANGELOG.md
git commit -m "docs(readme): 更新三 repo rollout 狀態" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```
