# Issue 46：Canonical local CI-parity preflight 計畫

**Issue:** `hamanpaul/paulsha-conventions#46`

**Dependency:** Issue 45 engine slice 已整合到 `feature/42-46-open-issues-batch`，避免同時修改 CLI/config/README。

**Builder boundary:** 本 repo 的 preflight engine、typed config schema、CLI entrypoint、tests、OpenSpec、README/CLAUDE、self-dogfood config 與 changelog fragment。`custom-skills` wrapper 另作下游 phase。

## Authority

- `paulsha-conventions` 擁有 pinned-engine resolution、PR context completeness、gate orchestration 與整體 exit verdict。
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
```

規則：

1. `--pr` 使用 `gh pr view` 取得真實 metadata；`--offline` 與 `--pr` 互斥。
2. 手動模式至少要求 title 與 body file；缺 body 不得輸出 `PREFLIGHT PASS`。
3. labels 可明確為空；base/head 可由 git 安全推導，輸出需列出 effective context。
4. 參數/設定錯誤 exit 2；任一 gate失敗 exit 1；全通過 exit 0。
5. 不以 shell 字串執行 repo-owned command。

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

## 下游 custom-skills phase

engine release 後，在 `hamanpaul/custom-skills` 獨立 branch：

1. `preflight-ci/scripts/preflight.sh` 改成只解析 skill UX 必需內容後 `exec policy-preflight "$@"`，或直接無邏輯轉送。
2. 移除 clone/fetch/checkout/pytest/OpenSpec orchestration複本。
3. 更新 skill 文件與 smoke tests，證明 wrapper 與 canonical CLI argv/exit code一致。
4. 不在兩個 repo 間共用 worktree 或 commit。

## 驗收

- `python3 -m pytest -q tests/test_preflight.py tests/test_rule_r08_policy_config_schema.py`
- `python3 -m pytest -q`
- `openspec validate --all`
- online/cached/offline/version-skew/context/gate-failure情境全部機械化。
- `python3 -m policy_check --repo .` 全綠。
- Foreign reviewer 無未處置 critical/important finding。
