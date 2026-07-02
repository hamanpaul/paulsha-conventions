# Tasks: auto-build-block

## 1. TDD RED

- [x] 1.1 在 `tests/test_rule_r08_policy_config_schema.py` 新增 `auto_build` 測試（覆蓋 spec 全部 scenario：非 mapping FAIL、subkey 型別 FAIL×3、完整/部分/空/未知 subkey/未宣告 PASS、無副作用）
- [x] 1.2 執行 `python3 -m pytest -q` 確認新測試以預期原因失敗（現行 R-08 對 `auto_build: make image` 回 PASS → 斷言 FAIL），保存 RED 證據

## 2. 實作 GREEN

- [x] 2.1 在 `policy_check/rules/r08_policy_config_schema.py` 新增 `auto_build` 驗證段（仿 `moc` 段：mapping 檢查 + `description` str + `setup`/`steps`/`artifacts`/`verify` list[str]；未知 subkey 放行；註明永不執行）
- [x] 2.2 執行 `python3 -m pytest -q` 全綠

## 3. Docs 同步（R-18）

- [x] 3.1 `README.md` 新增「`auto_build` 區塊」說明段（schema、範例、engine 只驗形狀永不執行的界線）
- [x] 3.2 新增 `changelog.d/30-auto-build-block.md`（`type: feat`，`issue: 30`）
- [x] 3.3 檢查 `docs/MOC.md` 是否需連結新產物（R-24）

## 4. Gate

- [x] 4.1 `python3 -m policy_check --repo .` 無任何 failure
- [ ] 4.2 code review 無未解 Critical/Important（含 fix 後 re-review）
