# Issue #46 Opus 5 對抗審查修復計畫

## 目標

目前狀態：對抗審查修復中

修正 PR #47（`feature/42-46-open-issues-batch`）在 exact head `b13da64`
接受 Claude Opus 5 對抗審查時發現的 authority 完整性缺陷與驗收缺口。
本輪只處理 #46 canonical local preflight，不改動 #42、#45 的既有行為。

## 已獨立複驗的判定

- F1 成立且阻擋 merge：skill wrapper 從 target repo 執行
  `python -m policy_check.preflight` 時，target 的 `policy_check` 會先於
  `PYTHONPATH` 中的 canonical engine 被載入。獨立 decoy 實驗確認：
  未加 `-P` 時執行 target module；加 `-P` 時執行 canonical module。
- F2 成立且阻擋 merge：目前測試只驗 `_resolve_engine` 有呼叫
  `_populate_cache`，沒有讓真正的 `_populate_cache` 建立 artifact。
- F3 成立且阻擋 merge：installer 測試沒有覆蓋「非 symlink 不可替換」
  與「不同 symlink 未帶 `--replace` 不可替換」。
- F4、F5、F7、F8 是成立但較低嚴重度的品質缺口，本輪一併以最小 diff 修正。
- F6 也接受修正：skill-driven full mode 必須有至少一個 typed
  `preflight.steps`；`preflight: {}` 或 `steps: []` 不得宣告
  `PREFLIGHT PASS`。`--policy-only` 仍是明確的 policy-only 入口。

## 實作邊界

允許修改：

- `skills/preflight-ci/scripts/preflight.sh`
- `policy_check/preflight.py`
- `tests/test_preflight.py`
- `tests/test_preflight_skill.py`
- `skills/preflight-ci/references/gotchas.md`
- `docs/MOC.md`
- `docs/superpowers/plans/2026-07-26-issue-46-opus5-review-repair.md`

不得修改其他檔案。若實作需要擴張邊界，停止並回報，不得自行越界。

## TDD 與修正工作

1. 先新增 wrapper shadowing 紅燈測試：在 target repo 放入 decoy
   `policy_check/preflight.py`，執行 wrapper 後必須證明載入的是 canonical
   engine。再將 wrapper 改為 Python safe-path 模式 `-P`；保留
   `PYTHONPATH`、target cwd、`--repo` 與 `--engine-source` 的既有契約。
2. 新增直接驅動 `_populate_cache` 的測試。可用受控 fake
   `_run_or_error` 搭配本地 git repo，但測試必須走真正的
   `_populate_cache`：
   - 只 fetch/checkout 傳入的完整 SHA，checkout 使用 detached mode；
   - 不得讀取或 fallback default branch；
   - 寫出的 manifest/artifact 必須可由 `_verify_cache` 接受；
   - 既存 artifact 必須 fail-closed。
3. 新增 installer 拒絕測試：
   - target 是真目錄或真檔時 exit 1，原內容保留；
   - target 是指向其他位置的 symlink、未帶 `--replace` 時 exit 1，
     原 symlink 保留。
4. engine resolver 失敗時也輸出最終 `PREFLIGHT FAIL`；不改 exit code。
5. `_is_canonical_checkout()` 的所有分支都實際回傳 `bool`。
6. skill full mode（有 `--engine-source` 且非 `--policy-only`）要求解析後
   至少一個 repo-owned step。空 block/空 steps 是 usage error（exit 2）；
   `--policy-only` 行為不變。
7. `docs/MOC.md` 不再把已封存的 #46 change 掛在 Active，並將 #46 plan
   狀態改為「對抗審查修復中」；完成覆審後由整合者收斂為通過。
8. gotchas 補上：
   - repo-owned step 失敗後如何依 `.paul-project.yml` 的 typed argv 重跑；
   - invalid cache artifact 的人工復原路徑，必須要求先核對精確
     `<repo>@<sha>` target，禁止給廣域刪除命令。

## 驗收

Codex builder 必須執行並附結果：

```bash
python3 -m pytest -q tests/test_preflight.py tests/test_preflight_skill.py
python3 -m pytest -q
python3 -m policy_check --repo .
openspec validate --all --strict
/home/paul_chen/.agents/skills/preflight-ci/scripts/preflight.sh --pr 47
```

主整合者會逐項檢查 diff、重跑全套 gate，並將修正後 exact head 再送
Claude Opus 5 對抗覆審。只有覆審無未處置 BLOCKER/MAJOR，且 GitHub
review threads 與 CI 都關閉，才可 merge。
