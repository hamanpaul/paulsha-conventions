# Issue #52 — runtime bundle activation 斷電級 crash recovery

- Issue: [#52](https://github.com/hamanpaul/paulsha-conventions/issues/52)（先 `gh issue view 52` 讀完整內容——已有安全邊界與 #48/#39 的責任分界都在裡面）
- 工作分支：`feature/issue-52-activation-crash-recovery`（由派工系統建立）
- 狀態：派工中
- 難度：本批最高——activation 狀態機 + journal + SIGKILL 級 fault injection

## 問題

activation（`policy_check/runtime_bundle/manager.py`）以 temp file/symlink、`os.replace` 與 in-process snapshot rollback 處理可捕捉的 step failure；但 `SIGKILL`／斷電／kernel 在多個 replace 之間終止時，可能留下 `state.json`、`current` symlink、兩個 stable launchers 與 managed skill link 的**混合世代**，需人工修復。

## 前置閱讀

1. `gh issue view 52`
2. `policy_check/runtime_bundle/manager.py` 的 activation 區段（state.json 寫入、current symlink 切換、launcher 安裝、skill link）
3. `docs/runtime-bundle-runbook.md`
4. **重要**：`gh pr diff 64` ——PR #64（已在 review 中，會先進 main）動了 `manager.py` 的 `_write_distribution_identity`／`_attest_installed_release` 呼叫點與 `verification.py` 的 `verify_installed_wheel_payload`。本分支設計時**避免改動這些函式的簽章與語意**，降低 rebase 衝突面。

## 實作要求（issue 的四個 checkbox）

1. **crash-recovery journal**：activation 的每一步（state.json、current、launcher×2、skill link）寫入 journal（append-only + fsync，或等價可機械驗證 protocol）。journal 本身必須 tamper-safe（digest 錨定或 atomic write），不得成為新攻擊面。
2. **重啟自動收斂**：下次啟動（或明確的 `recover` 入口）讀 journal，自動收斂到**完整舊世代或完整新世代**，不要求人工判讀混合狀態。收斂後 journal 歸檔或清除。
3. **fault-injection 測試**：對每一個中斷點做 subprocess hard-exit（`SIGKILL` 級）注入——子行程執行 activation、在指定步驟間 kill、驗證重啟後收斂正確。逐中斷點列舉，不得抽樣。
4. **runbook 更新**：`docs/runtime-bundle-runbook.md` 區分「caught failure transaction 保證」與「power-loss recovery 保證」兩節。

## 不得倒退的既有安全邊界

- 新舊 immutable release directory 都保留；不原地改寫 wheel/skill/artifact
- stable launcher 的 manifest/manager digest anchor 維持 fail-closed
- `policy_check/runtime_bundle/verification.py` 維持 **stdlib-only**（不得 import yaml 或 policy_check.identity）
- installed wheel、venv interpreter、`pyvenv.cfg`、bundle payload 的既有重驗全部保留

## Global constraints

- 版號語法 5 處禁區完全不改：`rules/r06_version_format.py:14`、`drift.py:20-21`、`drift.py:25-28`、`preflight.py:424`、`rules/r23_engine_pin_attestation.py:14-16`
- 新增 changelog fragment `changelog.d/52-activation-crash-recovery.md`（`type: feat`、`issue: 52`）
- PACKAGING 整合驗證：`python3 -m venv /tmp/pkg-venv && /tmp/pkg-venv/bin/pip install -e ".[test]" build`，然後 `PACKAGING=1 /tmp/pkg-venv/bin/python -m pytest tests/test_runtime_bundle_integration.py tests/test_wheel_offline.py -q` 必須全綠（系統 python 缺 build 模組，直接跑會誤 skip）
- 完成後 `python3 -m pytest -q` 全綠、`python3 -m policy_check --repo .` `fail: 0`

## 測試要求（TDD，先紅後綠）

新建 `tests/test_activation_crash_recovery.py`（fault-injection 逐中斷點）＋必要時擴充 `tests/test_runtime_bundle.py`。

## 驗收指令

```bash
python3 -m pytest -q tests/test_activation_crash_recovery.py
python3 -m pytest -q
python3 -m policy_check --repo .
# PACKAGING 驗證見 Global constraints
```

## 完成義務

全部變更 commit 到工作分支（conventional commit zh-tw，如 `feat(distribution): activation 斷電級 crash recovery journal 與自動收斂（#52）`）。**不開 PR**。worktree 必須乾淨。
