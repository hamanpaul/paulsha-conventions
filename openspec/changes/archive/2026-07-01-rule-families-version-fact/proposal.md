## Why

兩個互相關聯的治理缺口，合為一個 feature batch：

- **規則呈現太扁**：`policy_check` 報告把 26 條規則平鋪、依 `rule_id` 排序。規則重量／合併可行性分析已確認「合併 `rule_id`」是錯的工具（`R-NN` 是三重錨定的對外契約：規則原始碼 `exempt_label` + CLAUDE.md 白名單 + README 規則總表 + 測試 `get_rule("R-NN")` + 下游釘選）。正解是在**呈現層**用 family 分組——拿到「更少概念桶」的 UX，完全不動 `rule_id`／exemption label／inventory。
- **README 手抄版號漂移、無規則守**：`main` 上 canonical 真相一致，但 `README.md` 有手抄版號已漂移（`當前版本…現為 1.0.7`，落後三個 release），且沒有任何規則在驗證 README 裡自由書寫的版號。引擎**自己就有**能守這種漂移的規則——R-26 `generated_facts`——只是本 dogfood repo 一直沒對自己 opt-in。

對應設計 spec：`docs/superpowers/specs/2026-07-01-rule-families-and-version-fact-design.md`。

## What Changes

- **新增規則 family 呈現層分組**：`policy_check/rules/families.py`（中央有序分類）+ `report.py` 依 family 分組輸出（含 `OTHER` catch-all 與「body 逐條區塊數 == summary 計數」不變量）+ `cli.py` 傳入 `rule_id→family` 映射。**零 `rule_id`／exemption label／inventory 變動**。
- **README 訂正**：`L271` 版號改為 R-26 `repo-version` generated-fact marker（值 = `cat VERSION`）；`L269` 移除手抄規則數字面（規則清單屬 CHANGELOG／RELEASES）；`L21` 移除手抄 `policy_version` 字面（第二個漂移向量），改指向來源。
- **對本 repo dogfood R-26**：`.paul-project.yml` 宣告 `generated_facts`（`cat VERSION` ↔ README `repo-version` marker），使版號漂移在**每個 PR** 被擋。**不做 auto-fix**（R-26 FAIL 打槍 PR，由 agent 手動更新 marker）。
- **文件與 SOP**：`docs/MOC.md` 連結本 spec／plan（消 R-24 orphan WARN）；`RELEASES.md` 升版 SOP + release-process 記憶補「更新 README `repo-version` marker」。

## Capabilities

### New Capabilities
- `rule-family-grouping`: `policy_check` 報告依規則 family 分組呈現——中央有序分類（`families.py`）、`OTHER` 尾端 catch-all、「body 逐條區塊數恆等於 summary 計數」不變量、family 內按 `rule_id` 排序、`families=None` 時回舊平鋪（向後相容）；不觸及任何 `rule_id`／exemption label。

### Modified Capabilities
（無。R-26 規則行為不變——本 repo 僅 opt-in；README／`.paul-project.yml`／SOP 屬既有 R-26 能力的**應用**，非規格層行為變更。）

## Impact

- **新增**：`policy_check/rules/families.py`；測試 `tests/test_families.py`、`tests/test_report_grouping.py`。
- **修改（碼）**：`policy_check/report.py`（`emit` 分組 + OTHER catch-all）、`policy_check/cli.py`（傳 family map）。
- **修改（config/docs）**：`README.md`（版號 marker + 去字面 L21/L269）、`.paul-project.yml`（`generated_facts`）、`docs/MOC.md`（連 spec/plan）、`RELEASES.md`（SOP）。
- **相依**：無新增外部相依；R-26 用既有 `_marker_sync`（`cat VERSION` 於 CI 需可執行，POSIX `cat` 即可）。
- **版本**：flat profile，merge 後 PATCH bump 1.0.10 → 1.0.11（另走既有 release 流程）。
- **風險**：低。emit 唯一 caller 為 `cli.py`；per-rule 區塊格式與 exit code 契約不變；R-26 只宣告一個 entry。
