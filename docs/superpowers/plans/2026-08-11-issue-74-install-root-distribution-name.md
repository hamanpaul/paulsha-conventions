# Issue #74 第 3 項 — 安裝根目錄跟隨 distribution_name

- Issue: [#74](https://github.com/hamanpaul/paulsha-conventions/issues/74)（先 `gh issue view 74` 讀完整背景；第 1、2 項由另一分支回流，本 plan 只做第 3 項）
- 工作分支：`feature/issue-74-install-root`（由派工系統建立）
- 狀態：派工中

## 問題

runtime bundle 的預設安裝根目錄 `~/.local/share/paulsha-conventions` 是 `policy_check/runtime_bundle/manager.py` 的常數，未跟隨 distribution identity。arc-conventions 發行 fork（v1.0.16 實測）安裝後根目錄仍叫 `paulsha-conventions`——發行身分與磁碟足跡不一致。

## 實作要求

1. **安裝期以 manifest 為準推導根目錄**：預設 root = `~/.local/share/<manifest.distribution.distribution_name>`。注意 manager 於 bundle 安裝時以 vendored 形態獨立執行，**不得 import `policy_check.identity`**（安裝前套件不存在）；身分來源是 bundle 的 `manifest.json` 的 `distribution` 區塊（既有機制，`_write_distribution_identity` 已在用）。manifest 缺 `distribution`／`distribution_name` → fail-closed 中止安裝，不得回退寫死值。
2. **既有覆寫語意全部維持**：`--root` CLI 參數與 `PSC_CONVENTIONS_ROOT` env 優先於預設值（先 grep 現有解析順序，不改優先序，只改「最後的預設值」來源）。
3. **執行期（launcher／selection）一致性**：stable launcher、`current` symlink、`releases/<version>` 精確選版、digest anchor 等所有路徑推導必須與安裝期用同一來源；已安裝環境內可用安裝時寫入的資訊（launcher 內嵌 root、或 installed identity）取得，不得出現「安裝在 A 名下、launcher 找 B 名下」的分裂。逐一盤點 manager.py／preflight.py 中引用該預設 root 的位置（`grep -rn "paulsha-conventions" policy_check/ --include="*.py"` 過濾出 root 相關者）。
4. **release.yml 同步**：install smoke 中 `--root "$fake_home/.local/share/paulsha-conventions"` 與 `venv_python=...` 兩處、release notes 的預設路徑說明一處，改以 `${REPO#*/}` 或既有 glob 變數推導，不寫死。
5. **upstream 零行為變更**：upstream 的 `distribution_name` 就是 `paulsha-conventions`，推導結果與現值相同；既有安裝、`PSC_CONVENTIONS_ROOT` 使用者不受影響。
6. **文件同步**：`docs/runtime-bundle-runbook.md` 與 README 中提及預設安裝路徑處，改寫為「`~/.local/share/<distribution_name>`（upstream 即 `paulsha-conventions`）」。

## 不得倒退的既有保證

- `releases/<version>` 多版本共存與 `policy_version` 精確選版（缺版本 fail-closed 提示安裝，不自動降級）
- `current` 原子切換與 crash-recovery journal（#52）語意
- stable launcher 的 manifest/manager digest anchor fail-closed
- `policy_check/runtime_bundle/verification.py` 維持 stdlib-only

## 測試要求（TDD，先紅後綠）

- 安裝根目錄推導：manifest 帶 `distribution_name: arc-conventions` → root 為 `~/.local/share/arc-conventions`（以 fake home 驗證）；upstream manifest → 現值不變
- manifest 缺 `distribution`／`distribution_name` → 安裝 fail-closed
- `--root`／`PSC_CONVENTIONS_ROOT` 覆寫優先序不變
- `PACKAGING=1` 整合測試全綠（venv：`python3 -m venv /tmp/ir-venv && /tmp/ir-venv/bin/pip install -e ".[test]" build`；勿用系統 python）

## Global constraints

- 版號語法 5 處禁區不改：`rules/r06_version_format.py:14`、`drift.py:20-21`、`drift.py:25-28`、`preflight.py:424`、`rules/r23_engine_pin_attestation.py:14-16`
- 新增 changelog fragment `changelog.d/74-install-root-distribution-name.md`（`type: feat`、`issue: 74`）
- 完成後 `python3 -m pytest -q` 全綠、`python3 -m policy_check --repo .` `fail: 0`

## 驗收指令

```bash
python3 -m pytest -q tests/test_runtime_bundle.py
python3 -m pytest -q
python3 -m policy_check --repo .
# PACKAGING 驗證見測試要求
```

## 完成義務

全部變更 commit 到工作分支（conventional commit zh-tw，如 `feat(distribution): 安裝根目錄跟隨 distribution_name（#74）`）。**不開 PR**。worktree 必須乾淨。
