# Issue #61 — policy_check 啟動時比對執行中引擎版本與 policy_version 宣告

- Issue: [#61](https://github.com/hamanpaul/paulsha-conventions/issues/61)（先 `gh issue view 61` 讀完整內容，內含 IntelliDbgKit 實際事故時間線）
- 工作分支：`feature/issue-61-engine-version-gate`（由派工系統建立，勿自行改分支）
- 狀態：派工中

## 問題

`policy_check` 不檢查「執行中的引擎版本」與 repo 宣告的 `policy_version` 是否一致。舊引擎（1.0.10）讀到 `policy_version: 1.0.15` 不但不抱怨，R-20 還回報綠燈——本機 preflight 可長期比 CI 弱且無任何訊號。

## 實作要求

1. **啟動時比對並 fail loud**：載入 `.project-policy.yml` 後，比對 `policy_version` 與執行中引擎版本；不符 → 以 configuration error 等級失敗（比照 `Missing .project-policy.yml` 的處理路徑），訊息必須同時列出：引擎版本、宣告版本、建議重裝指令。
2. **報告表頭顯著標示引擎版本**：`# Policy Check Report` 之後加一行執行中引擎版本（含來源：installed package 或 source checkout）。
3. **引擎版本的取得沿用既有機制**：優先 `importlib.metadata.version("policy-check")`，source checkout fallback 讀 repo 的 `VERSION`。不得發明第三套版本來源。注意 PEP 440 正規化（`-fix.N` ↔ `.postN`，見 `preflight.py:424` 的既有轉換——**該行屬版號語法禁區，只能呼叫不能改**）。
4. **不得誤殺的情境**（各需測試）：
   - conventions repo 自身 source checkout 開發：引擎版本來源=repo `VERSION`，與 `policy_version` 天然一致，必須通過
   - release PR 上 `VERSION` 先行 bump 的窗口：比照 R-07 的 `release:*` label 豁免邏輯，帶 release label 時降為 WARN
   - 無法取得引擎版本（極端環境）：fail-closed，報 configuration error，不得靜默跳過
5. 訊息語言比照既有規則輸出（英文 message 格式）。

## 測試要求（TDD，先紅後綠）

新建 `tests/test_engine_version_gate.py`：版本相符通過／不符 fail-loud（訊息含雙方版本）／release label 降 WARN／版本取得失敗 fail-closed／報告表頭含引擎版本。

## Global constraints

- 版號語法 5 處禁區完全不改：`rules/r06_version_format.py:14`、`drift.py:20-21`、`drift.py:25-28`、`preflight.py:424`、`rules/r23_engine_pin_attestation.py:14-16`
- 新增 changelog fragment `changelog.d/61-engine-version-gate.md`（frontmatter `type: fix`、`issue: 61`；body 一條 zh-tw 描述）
- 完成後 conventions repo 自身 `python3 -m policy_check --repo .` 必須仍 `fail: 0`
- 既有測試不得破壞

## 驗收指令

```bash
python3 -m pytest -q tests/test_engine_version_gate.py
python3 -m pytest -q
python3 -m policy_check --repo .
```

## 完成義務

全部變更 commit 到工作分支（conventional commit zh-tw，如 `fix(engine): 啟動時比對引擎版本與 policy_version 宣告（#61）`）。**不開 PR**——PR 由整合端統一建立。worktree 必須乾淨（無未 commit 變更）。
