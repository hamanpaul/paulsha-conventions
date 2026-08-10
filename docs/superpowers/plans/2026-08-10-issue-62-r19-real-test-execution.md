# Issue #62 — R-19 結構化偵測實際測試執行 + canonical tests.yml 骨架

- Issue: [#62](https://github.com/hamanpaul/paulsha-conventions/issues/62)（先 `gh issue view 62` 讀完整內容——三個失效模式的證據、三個 repo 的三種修法、與分階段上線策略都在裡面）
- 工作分支：`feature/issue-62-r19-real-test-execution`（由派工系統建立）
- 狀態：派工中

## 問題

R-19（`policy_check/rules/r19_ci_tests.py`）對 workflow 檔做整檔 regex，一行註解（`# pytest ...`）或 `pip install pytest` 就能滿足；且被廣泛複製的 tests.yml 骨架有 `ls a b` 雙 glob 偵測 bug，測試被靜默跳過卻回報綠燈。

## 實作要求（對應 issue 建議 1、3、4；建議 2 的 preflight-ci 閘門屬 out of scope，見下）

1. **R-19 改為結構化偵測**：
   - 解析 workflow YAML（`yaml.safe_load`），只檢視 `jobs.*.steps[].run` 內容；忽略註解與 `name:`
   - 排除安裝行：`pip install`、`apt-get install`、`npm i`/`npm install` 等（安裝行中出現 pytest 不算執行測試）
   - step 帶 `if:` 條件 → 該命中至少 **WARN**，訊息說明 gate 可能為條件式；若 `if:` 引用同 job 內 step output → 訊息額外標註「可被靜默跳過的高風險樣式」
   - YAML 解析失敗的 workflow → 回退整檔字串比對並 WARN（不得因單一壞檔讓規則 crash）
2. **分階段上線（issue 影響評估的要求）**：本版對「先前會 pass、新偵測抓到的繞過樣式」（僅註解命中、僅安裝行命中）輸出 **WARN**（訊息預告下一版轉 FAIL）；「repo 有測試但完全沒有任何 workflow 實際執行測試」維持既有 **FAIL**。嚴格模式以規則設定開關（`.project-policy.yml` 的 r19 區塊，經 R-08 schema 驗證）供 repo 自行提前啟用 FAIL。
3. **canonical tests.yml 骨架**：新增 `examples/workflows/tests.yml`（或依 repo 既有 examples 結構擇一目錄），採 issue 驗證過的偵測：
   ```bash
   if [ -d tests ] && [ -n "$(find tests -maxdepth 1 \( -name 'test_*.py' -o -name '*_test.py' \) -print -quit)" ]; then
   ```
   附註解說明三種已驗證情境與舊骨架的缺陷根因。
4. **反例 fixtures**（issue 建議 4）：在 `tests/fixtures/ci-tests/` 補三個 fixture——僅註解提到 pytest（應 WARN/嚴格模式 FAIL）、僅 `pip install pytest`（同上）、`run: pytest` 被恆 false `if:` 守衛（至少 WARN）。

## Out of scope

- preflight-ci 的「CI 測試閘門有效性」檢查（issue 建議 2）：牽動 preflight 流程，另開 scoped issue 處理，本分支不做。
- 下游 repo 的骨架替換 rollout。

## 測試要求（TDD，先紅後綠）

更新 `tests/test_rule_r19_ci_tests.py`：三個反例 fixture 各有紅→綠測試；既有正例不得破壞；嚴格模式開關測試。

## Global constraints

- 版號語法 5 處禁區完全不改：`rules/r06_version_format.py:14`、`drift.py:20-21`、`drift.py:25-28`、`preflight.py:424`、`rules/r23_engine_pin_attestation.py:14-16`
- 新增 changelog fragment `changelog.d/62-r19-real-test-execution.md`（`type: fix`、`issue: 62`）
- R-08 schema 若新增 r19 設定區塊，schema 與測試同步更新
- conventions repo 自身 CI（`.github/workflows/`）必須通過新 R-19——若自身 workflow 被新偵測抓到，先修自身 workflow
- 完成後 `python3 -m policy_check --repo .` 必須仍 `fail: 0`

## 驗收指令

```bash
python3 -m pytest -q tests/test_rule_r19_ci_tests.py
python3 -m pytest -q
python3 -m policy_check --repo .
```

## 完成義務

全部變更 commit 到工作分支（conventional commit zh-tw，如 `fix(rules): R-19 改為結構化偵測實際測試執行（#62）`）。**不開 PR**。worktree 必須乾淨。
