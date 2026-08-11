# Issue #77 — smoke fixture 的 /home 路徑 R-21 誤中 + preflight 摘要診斷改善

- Issue: [#77](https://github.com/hamanpaul/paulsha-conventions/issues/77)（先 `gh issue view 77` 讀完整內容——含 2026-08-11 兩小時定位過程與兩項建議）
- 工作分支：`feature/issue-77-smoke-r21`（由派工系統建立）
- 狀態：派工中

## 問題（兩項，同分支處理）

**A.** `manager._make_smoke_repo`（`policy_check/runtime_bundle/manager.py`）把 `sys.executable` 逐字寫進 smoke fixture 的 `.project-policy.yml`（preflight step argv）。fixture 宣告 `tier: shareable`，R-21 的 `_STRUCTURAL` 樣式（`r21_secret_scan.py:14`，`/home/[a-z_][a-z0-9_-]*/`）命中任何 /home 下的 interpreter → install 的 smoke preflight 必 FAIL。實測影響：開發者用 repo 內 `.venv`（/home 下）跑 `PACKAGING=1` 整合測試必炸；真實部署 `PYTHON_BIN` 在 /home 亦然。

**B.** preflight 的 policy gate 摘要只取輸出末 4 行（`preflight.py:847` 附近 `lines[-4:]`），失敗規則名常被 R-24/R-25 的尾行擠掉——把「哪條規則失敗」變成考古工作。

## 實作要求

**A. fixture 自我豁免（issue 建議修法 1）**
- `_make_smoke_repo` 生成的 config 加：
  ```yaml
  secret_scan:
    allow:
      - ".project-policy.yml"
  ```
  （`allow` 為 glob 字串清單，見 `r21_secret_scan.py:116` 與 `tests/fixtures/secret-scan/shareable-allowlisted/`；R-08 schema 已支援，見 `r08_policy_config_schema.py:92`）
- 附註解說明理由：synthetic fixture 的 argv 必須內嵌絕對 interpreter 路徑（minimal env 無法靠 PATH），路徑本身非機密，屬 R-21 允許的合法引用豁免

**B. preflight 摘要優先保留失敗行**
- `preflight.py` 的 policy gate 摘要（`lines[-4:]` 處）改為：有 `:x:` 行時優先納入（如 前 3 條 `:x:` 行 + 末 2 行），無失敗行維持現行為；800 字元上限不變
- 摘要語意不變（僅擷取策略改變），任何 gate 判定邏輯不得動

## 測試要求（TDD，先紅後綠）

- **A 回歸測試**：monkeypatch `manager.sys.executable` 為 `/home/someuser/.venv/bin/python3` 樣式路徑 → `_make_smoke_repo` 產出的 fixture 直接跑 R-21（參考 `tests/test_rule_r21_secret_scan.py` 的 `make_ctx` 樣式）必須 pass；修復前此測試必須紅（`/home/` 路徑無豁免時 structural 命中）
- **B 單元測試**：對摘要函式餵含 `:x:` 行的多行輸出 → 摘要包含 `:x:` 行；無 `:x:` → 行為同現行
- `PACKAGING=1` 整合測試在 **/home 下的 venv** 跑必須全綠（這是本 issue 的原始症狀；venv 建在 worktree 內即符合條件）——修復前可先確認紅

## Global constraints

- 版號語法 5 處禁區不改：`rules/r06_version_format.py:14`、`drift.py:20-21`、`drift.py:25-28`、`preflight.py:424`、`rules/r23_engine_pin_attestation.py:14-16`
- R-21 的偵測樣式本身（`_STRUCTURAL` 等）**不得放寬**——修的是 fixture 與摘要，不是掃描器
- `verification.py` 維持 stdlib-only
- 新增 changelog fragment `changelog.d/77-smoke-fixture-r21.md`（`type: fix`、`issue: 77`）
- 完成後 `python3 -m pytest -q` 全綠、`python3 -m policy_check --repo .` `fail: 0`

## 驗收指令

```bash
python3 -m pytest -q tests/test_runtime_bundle.py tests/test_preflight.py
python3 -m pytest -q
python3 -m policy_check --repo .
# PACKAGING（venv 刻意建在 /home 下的 worktree 內）：
python3 -m venv .venv-home && ./.venv-home/bin/pip install -e ".[test]" build
PACKAGING=1 ./.venv-home/bin/python -m pytest tests/test_runtime_bundle_integration.py tests/test_wheel_offline.py -q
```

## 完成義務

全部變更 commit 到工作分支（conventional commit zh-tw，如 `fix(distribution): smoke fixture 自我豁免 R-21 並改善 preflight 失敗摘要（#77）`）。**不開 PR**。worktree 必須乾淨（`.venv-home` 屬未追蹤驗證產物，完成前刪除）。
