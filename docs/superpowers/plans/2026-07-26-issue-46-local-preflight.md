# Issue 46：Canonical local CI-parity preflight 計畫

**Issue:** `hamanpaul/paulsha-conventions#46`

**Dependency:** Issue 45 engine slice 已整合到 `feature/42-46-open-issues-batch`，避免同時修改 CLI/config/README。

**Builder boundary:** 本 repo 的 canonical `preflight-ci` skill、安裝入口、preflight engine、typed config schema、CLI entrypoint、tests、OpenSpec、README/CLAUDE、self-dogfood config 與 changelog fragment；舊 skill authority 另以 source repo PR 移除。

## Authority

- `paulsha-conventions` 擁有 pinned-engine resolution、PR context completeness、gate orchestration 與整體 exit verdict。
- `paulsha-conventions/skills/preflight-ci` 擁有 agent-facing routing 與落地安裝；skill
  直接使用相鄰的 conventions source checkout，不依賴 GitHub Actions workflow
  作為主要 resolver 或過濾入口。
- 下游 repo 透過 `.paul-project.yml` 擁有要執行的 validation/test command 與 timeout。
- preflight 不猜 `pytest`、Gradle、Make 或 OpenSpec；本 repo 可在自己的 config 宣告 pytest/OpenSpec 以 dogfood。
- GitHub/GitLab 最終 merge gate仍是 authority；local preflight 只提供 CI-parity 的前移證據。

## CLI

新增 canonical entrypoint：

```text
policy-preflight
python3 -m policy_check.preflight
```

支援：

```text
--repo
--pr
--pr-title
--pr-body-file
--pr-labels
--base
--head
--skip-tests
--policy-only
--offline
--cache-dir
--engine-source
```

規則：

1. `--pr` 使用 `gh pr view` 取得真實 metadata；`--offline` 與 `--pr` 互斥。
2. 手動模式至少要求 title 與 body file；缺 body 不得輸出 `PREFLIGHT PASS`。
3. labels 可明確為空；base/head 可由 git 安全推導，輸出需列出 effective context。
4. 參數/設定錯誤 exit 2；任一 gate失敗 exit 1；全通過 exit 0。
5. 不以 shell 字串執行 repo-owned command。
6. Skill wrapper 固定注入相鄰的 canonical `--engine-source`；source checkout
   remote、VERSION、HEAD 與 clean status 任一不符即 fail-closed。

## Repo-owned config

`.paul-project.yml` 新增 optional：

```yaml
preflight:
  steps:
    - name: openspec
      kind: validation
      argv: ["openspec", "validate", "--all"]
      when_path_exists: "openspec"
      timeout_seconds: 300
    - name: tests
      kind: tests
      argv: ["python3", "-m", "pytest", "-q"]
      timeout_seconds: 1200
```

R-08 驗證：

- `preflight` 是 mapping；
- `steps` 是 list of mapping；
- `name` 非空且不可重複；
- `kind` 僅 `validation|tests`；
- `argv` 是非空 `list[str]`；
- `cwd`、`when_path_exists` 若存在必須為 repo-relative、不可跳出 repo；
- `timeout_seconds` 是正整數；
- unknown subkey 維持現有 lenient policy，但已知欄位型別錯誤必須 FAIL。

`--skip-tests` 只跳過 `kind: tests`；`--policy-only` 跳過所有 repo-owned steps。

## Pinned engine resolution

1. 解析下游 `.github/workflows/policy-check.yml`：
   - `policy_engine_ref` 必須是完整 SHA；
   - 解析 reusable workflow owner/repo；
   - `uses:` SHA 與 `policy_engine_ref` 若同時存在必須一致。
2. pip mode 以 `.paul-project.yml` 的 `policy_version` 對照已安裝 `policy-check` distribution；不符即 FAIL。
3. source/SHA mode 的 cache 以 `engine repo + full SHA` 為 immutable key，另存 manifest；不能把「某個 checkout 剛好在該 SHA」當無驗證 cache。
4. online mode 可 clone/fetch缺少的 exact SHA；不得 fallback 到 default branch 或其他 installed version。
5. 本 engine repo self-dogfood 可使用 current checkout，但必須核對 `VERSION` 與 config。

## Offline contract

`--offline`：

- 不執行 `gh`、`git clone`、`git fetch` 或其他 network resolver。
- 只接受 matching installed distribution 或 manifest/hash 驗證通過的 exact-SHA cache。
- 缺 artifact 時明確列出缺少的 repo/SHA/version 並 FAIL。
- PR metadata 只能由 CLI/file 提供。
- 測試以 fake runner 斷言 offline path 沒有 network-capable resolver invocation。
- repo-owned commands 仍由 repo authority 負責；preflight 必須在輸出中明示它只保證自身 resolver offline。

## 執行與輸出

1. policy gate 以 resolved engine 啟動新 subprocess，帶完整 PR/base/head/visibility context。
2. 每個 repo-owned step 使用 typed argv、resolved repo-relative cwd、timeout 與 sanitized environment。
3. stdout 逐 gate 顯示 `PASS/FAIL/SKIP`、duration 與 effective engine identity；不得印 token 或整份 GitHub metadata。
4. 只有全部 selected gates pass 才輸出 `PREFLIGHT PASS`。

## TDD / 文件

1. 新增 `tests/test_preflight.py`，以 fake git/gh/subprocess/cache 釘住：
   - fresh online cache；
   - cached offline；
   - missing offline artifact；
   - installed-version skew；
   - uses/ref mismatch；
   - incomplete PR context；
   - policy/OpenSpec/tests 任一 fail；
   - `skip-tests` / `policy-only`；
   - path traversal 與 timeout。
2. 擴充 R-08 tests。
3. 建立 active OpenSpec change `canonical-local-preflight`。
4. 更新 `pyproject.toml` console script、README 中英 Local/Offline Preflight、canonical `CLAUDE.md` checklist。
5. `.paul-project.yml` 新增本 repo dogfood steps；R-16 CLI registry/README help marker同步。
6. 修復本 repo 既有 OpenSpec baseline：`account-defaults` 與 `new-project-bootstrap` canonical spec 補齊實質 `## Purpose`，使 self-dogfood 的 `openspec validate --all` 可通過；不得以 skip 隱藏。
7. 新增 `changelog.d/46-local-preflight.md`，`type: feat`、`issue: 46`。

## Skill ownership migration

1. canonical skill 位於 `skills/preflight-ci/`，wrapper 只定位 target repo 與相鄰
   engine source，再委派 `policy_check.preflight`。
2. `scripts/install-preflight-skill.sh` 將 `~/.agents/skills/preflight-ci` 指向本
   repo；只允許替換 symlink，不刪除真目錄。
3. 舊 source repo 以獨立 branch/PR 移除 `preflight-ci`，並把 migration 指向
   `hamanpaul/paulsha-conventions`；不得在兩個 repo 共用 commit。
4. 遷移順序固定為：新 authority 通過測試 → 切換 symlink 並 smoke → 舊
   authority removal PR。Rollback 只需把 symlink 指回舊 checkout。
5. 舊 working tree 尚未提交的 `PSC_PREFLIGHT_PYTHON` 相容需求由新 wrapper
   承接；project test interpreter 則改由 repo-owned step `argv` 擁有。

## 驗收

- `python3 -m pytest -q tests/test_preflight.py tests/test_rule_r08_policy_config_schema.py`
- `python3 -m pytest -q`
- `openspec validate --all`
- online/cached/offline/version-skew/context/gate-failure情境全部機械化。
- `python3 -m policy_check --repo .` 全綠。
- Foreign reviewer 無未處置 critical/important finding。

## 對抗審查判定

- 未處置的實作缺陷或驗收缺口 ⇒ FAIL。
- 已明文承認、影響分析有界且在文件列管的殘餘風險，不單獨構成 FAIL；reviewer 若不接受，必須具體反駁其影響分析。
