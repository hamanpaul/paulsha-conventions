# Issue #46 Opus 5 對抗審查修復計畫

## 目標

目前狀態：Opus 5 第二輪發現 2 項 MAJOR，窄幅修復中

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

## 主驗收與第二輪覆審契約

- Codex Spark candidate：`6bd273f`
- 整合 head：`e5e8c33`
- targeted tests：42 passed
- full suite：470 passed、1 skipped
- policy：26 pass、0 fail、0 warn
- OpenSpec：18 passed、0 failed
- canonical `preflight-ci --pr 47`：PASS

第一輪 F1 的核心 authority bypass 成立，但「PEP 420 namespace package 不需
`__init__.py` 即可覆寫 canonical regular package」這項細節不成立；獨立複驗以
target regular package（含 `__init__.py`）重現。第二輪 reviewer 必須依此修正後
前提檢查 `-P` 是否封閉實際 bypass，不得沿用已被實驗反駁的 namespace 論證。

第二輪判定契約：未處置的缺陷／驗收缺口為 FAIL；已明文承認、影響分析有界且
列管的殘餘風險不單獨構成 FAIL。輸出最多 10 項 BLOCKER／MAJOR，每項須含
`path:line`、失敗情境與必要修正；若沒有則輸出 `VERDICT: PASS / NONE`。

## 第二輪 findings 與第三輪窄幅修復

第二輪 Opus 5 判定 `FAIL / 2 MAJOR`。主整合者已用直接呼叫分別重現：

- `_run_steps()` 遇不可執行 command 時逸出 `PermissionError`；
- `_populate_cache()` 遇不可寫／不存在的 cache parent 時逸出裸
  `OSError`，若由 `main()` resolver 路徑觸發便沒有最終 verdict。

本輪只允許修改：

- `policy_check/preflight.py`
- `tests/test_preflight.py`
- `docs/superpowers/plans/2026-07-26-issue-46-opus5-review-repair.md`
- `docs/MOC.md`

必要行為：

1. `_run_steps()` 捕捉 `OSError` 與輸出解碼錯誤，該 step 記為 FAIL，
   但仍繼續後續 steps，最後由 `main()` 輸出 `PREFLIGHT FAIL`。
2. `_run_or_error()` 將 `OSError` 與輸出解碼錯誤正規化成既有的
   `PreflightGateError`／`PreflightUsageError`。
3. `main()` engine resolver 邊界收斂 resolver 內 filesystem／encoding
   例外，輸出 `engine: FAIL` 與 `PREFLIGHT FAIL`，return 1，不得印 traceback。
4. 補測試證明 `PermissionError` step 不會中斷後續 step，以及
   `_resolve_engine` 拋 `PermissionError`／`UnicodeError` 時 final verdict
   與 exit code 正確。

以下第二輪非阻擋觀察列為有界 residual，不在本窄修復擴張：

- engine repo regex 的 dot-segment/path containment 強化；
- 直接 `--engine-source` 與 orchestrator import path 的額外交叉證明；
- `-P` 安全不變式升格為獨立 OpenSpec requirement；
- 所有 conditional steps 都 SKIP 時的 policy 語意；
- wrapper 的 Python 3.11 最低版本提示。

這些不影響 wrapper 的實際 `-P` authority 修補或本輪兩個 verdict escape，
後續由 #48 的 installed-bundle／selector contract 一併重裁決。
