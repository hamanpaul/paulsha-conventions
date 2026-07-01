## 1. Family 分類核心（families.py）

- [ ] 1.1 先寫失敗測試 `tests/test_families.py`：`family_of("R-05")=="VERSION"`、未知 id 回 `"OTHER"`、`ordered_families()` 順序、以及**完整性**（`registry.load_all()` 每個 `rule_id` 在 `FAMILIES` 恰好一次、無未知 id）
- [ ] 1.2 實作 `policy_check/rules/families.py`：`FAMILIES: list[tuple[str, tuple[str,...]]]`（11 family，順序即輸出序）、`family_of`、`ordered_families`
- [ ] 1.3 測試轉綠

## 2. report.py 分組 + OTHER catch-all

- [ ] 2.1 先寫失敗測試 `tests/test_report_grouping.py`：分組輸出含 family 標題、family 順序正確、family 內按 `rule_id`；`families=None` 等同舊平鋪；summary 與 exit code 不變；**OTHER 不變量**——給一個 `rule_id` 不在 map 的假 result，斷言它仍出現在 `### OTHER` 區段、且 body 逐條區塊數 == summary 計數
- [ ] 2.2 改 `report.emit(results, families=None)`：依 `ordered_families()` 分組 + 尾端 `OTHER` catch-all；保留 summary／per-rule 區塊格式／`return 1 if fails`
- [ ] 2.3 測試轉綠

## 3. cli.py 接線

- [ ] 3.1 `cli.run` 組 `families = {r.rule_id: families.family_of(r.rule_id) for r in rules}`，傳給 `emit(results, families)`
- [ ] 3.2 手動驗 `python3 -m policy_check --repo .` 輸出已分組、summary/exit code 不變；`--only R-05,R-06` 只印有結果的 family

## 4. README 訂正

- [ ] 4.1 L271 版號改為 `repo-version` generated-fact marker 區塊（值 = 動工時 `cat VERSION`，現為 `1.0.10`，只一行）；確認 README 內無第二個 `repo-version` BEGIN/END pair
- [ ] 4.2 L269 移除手抄「R-01~R-23 完整實作」規則數字面，改述不綁數字、指向 RELEASES/CHANGELOG
- [ ] 4.3 L21 移除手抄 `policy_version: 1.0.10` 字面，改指向 `.paul-project.yml` / `VERSION`

## 5. R-26 dogfood

- [ ] 5.1 `.paul-project.yml` 加 `generated_facts: [{command: "cat VERSION", reflected_in: "README.md", marker: "repo-version"}]`
- [ ] 5.2 驗證本 repo R-26：green（marker 對齊 → PASS，由 NA 轉 PASS）；red（tmp fixture/monkeypatch 改 VERSION 或 marker 使不符 → FAIL），不污染真檔
- [ ] 5.3 確認 `python3 -m policy_check --repo .` R-08 對新 `generated_facts` 通過、無非預期自我 FAIL

## 6. 文件對齊與 SOP

- [ ] 6.1 `docs/MOC.md` 連結本設計 spec + plan（Plans／Specs 段），消 R-24 orphan WARN
- [ ] 6.2 `RELEASES.md` 升版 SOP + release-process 記憶：bump 清單補「更新 README `repo-version` marker（＝新 `VERSION`）」

## 7. 收尾

- [ ] 7.1 新增 changelog fragment `changelog.d/<slug>.md`（type: feat）
- [ ] 7.2 全 suite 綠（`python3 -m pytest -q`）
- [ ] 7.3 `python3 -m policy_check --repo .` 無 fail（R-24 orphan WARN 已由 6.1 消除）
- [ ] 7.4 openspec validate 通過
