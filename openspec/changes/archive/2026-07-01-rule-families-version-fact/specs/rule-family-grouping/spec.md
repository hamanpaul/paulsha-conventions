## ADDED Requirements

### Requirement: 報告依規則 family 分組呈現

`policy_check` 報告 SHALL 依中央有序分類（`policy_check/rules/families.py` 的 `ordered_families()`）將規則結果分組輸出：每個 family 一個標題，family 內的規則按 `rule_id` 排序。分類定義集中於單一模組，提供 `family_of(rule_id) -> str` 與 `ordered_families() -> list[str]`。

#### Scenario: 多 family 結果依序分組
- **WHEN** `emit(results, families)` 收到跨多個 family 的結果與 `rule_id→family` 映射
- **THEN** 輸出依 `ordered_families()` 的順序列出 family 標題，各 family 標題下僅列屬於該 family 的規則，且 family 內按 `rule_id` 遞增排序

#### Scenario: 篩選後空 family 不輸出
- **WHEN** 以 `--only` 篩選後某 family 無任何結果
- **THEN** 該 family 的標題不輸出

### Requirement: body 區塊數恆等於 summary 計數（OTHER catch-all）

分組輸出 SHALL 保證「body 中逐條規則區塊數 == summary 的規則總數」——任何被 summary 計數的結果都不得從 body 消失。凡 `rule_id` 不在 `families` 映射內、或其 family 不在 `ordered_families()` 內者，SHALL 收納於尾端固定的 `OTHER` 區段。

#### Scenario: 未分類規則仍出現在 body
- **WHEN** 某結果的 `rule_id` 不在 `families` 映射（或 `family_of` 回 `"OTHER"`）
- **THEN** 該結果仍出現在報告 body 的 `OTHER` 區段（不被靜默漏印），且 body 逐條區塊數等於 summary 計數

### Requirement: 向後相容與契約不變

分組 SHALL 不改變既有輸出契約：`emit(results, families=None)` 在未提供 `families` 時回退為原本「依 `rule_id` 平鋪」行為；每條規則的 icon／message／exempt／detail 區塊格式不變；頂部 summary 計數不變；`return 1 if fails else 0` 的 exit code 不變；不觸及任何 `rule_id` 或 exemption label。

#### Scenario: 未提供 families 時回舊平鋪
- **WHEN** `emit(results)` 未帶 `families` 參數
- **THEN** 輸出等同原本依 `rule_id` 排序的平鋪清單，summary 與 exit code 不變

#### Scenario: 分組不影響 exit code
- **WHEN** results 內含至少一個 FAIL
- **THEN** 無論是否分組，`emit` 回傳 1

### Requirement: 分類完整性可驗

`FAMILIES` 分類 SHALL 對 `registry.load_all()` 的每個 `rule_id` 恰好歸屬一個 family，且不含未知或重複的 `rule_id`；此完整性 SHALL 由測試守護，使新增規則漏分類時測試失敗。

#### Scenario: 每個規則恰好一個 family
- **WHEN** 測試枚舉 `registry.load_all()` 的所有 `rule_id`
- **THEN** 每個 `rule_id` 在 `FAMILIES` 中恰好出現一次，且 `FAMILIES` 不含 registry 以外的 `rule_id`
