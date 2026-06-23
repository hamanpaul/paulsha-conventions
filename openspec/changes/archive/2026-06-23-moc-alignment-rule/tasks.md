## 1. R-08 驗證 moc 區塊

- [x] 1.1 撰寫 R-08 測試（fixtures）：`moc.triggers` 非 list[str]→FAIL、`moc.static`/`moc.map` 非 str→FAIL、合法→PASS
- [x] 1.2 擴充 `policy_check/rules/r08_policy_config_schema.py`：驗 `moc`（mapping、`static`/`map` 為 str、`triggers` 為 list[str]）
- [x] 1.3 R-08 測試全綠

## 2. R-24 骨架（opt-in / NA）

- [x] 2.1 撰寫 R-24 測試：未設 `moc`→PASS(NA)；`policy-exempt:moc-alignment`→SKIP
- [x] 2.2 新增 `policy_check/rules/r24_moc_alignment.py`：讀 `ctx.config["moc"]`；無→NA PASS；`exempt_label = "policy-exempt:moc-alignment"`
- [x] 2.3 確認 registry 依 `rNN_` 自動載入 R-24；`tests/test_rules_presence.py` 補 R-24
- [x] 2.4 測試全綠

## 3. 靜態鮮度瓣（WARN）

- [x] 3.1 撰寫測試：trigger 命中且 `moc.static` 不在 diff→WARN；trigger 命中且 static 在 diff→不報；無 diff context→不硬報
- [x] 3.2 實作：對 `ctx.changed_files` 比對 `moc.triggers` glob；命中而 `moc.static` 不在 changed_files → WARN
- [x] 3.3 測試全綠

## 4. 動態連結懸空瓣（diff-aware FAIL/WARN）

- [x] 4.1 撰寫測試：map 連結指向本次刪除的產物→FAIL；陳年（base/head 皆無）→WARN；無 diff context→降 WARN
- [x] 4.2 實作：重用 R-22 的 link/path token 抽取，掃 `moc.map`，對象限 `openspec/changes/**`、`docs/superpowers/{specs,plans}/**`；以 `base..head` 分級
- [x] 4.3 測試全綠

## 5. 動態連結孤兒瓣（WARN）

- [x] 5.1 撰寫測試：存在 active openspec change / plan / spec 未被 map 連結→WARN；全連結→不報；archived 不算；確認此瓣永不 FAIL
- [x] 5.2 實作：列舉 `openspec/changes/*`（排除 `archive/`）、`docs/superpowers/plans/*` 與 `docs/superpowers/specs/*`，比對 `moc.map` 連結集合，缺者 WARN（不 FAIL）
- [x] 5.3 測試全綠

## 6. 嚴重度彙整與輸出

- [x] 6.1 撰寫測試：三瓣同時觸發時 status 取最嚴（FAIL > WARN > PASS）、detail 分段列出
- [x] 6.2 實作彙整：任一瓣 FAIL→FAIL；否則任一 WARN→WARN；皆無→PASS
- [x] 6.3 測試全綠

## 7. 慣例檔 / 文件 / dogfood

- [x] 7.1 `CLAUDE.md`：claim-done 補 R-24；白名單加 `policy-exempt:moc-alignment`；新增「MOC 動態狀態對齊（advisory，Copilot）」段
- [x] 7.2 `README.md` 規則總覽補 R-24；`CHANGELOG.md [Unreleased]` 補 entry
- [x] 7.3 本 repo 自宣告 `moc`（map 連到自身 `openspec/changes` 與 `docs/superpowers`）dogfood；`python3 -m policy_check --repo .` R-24 通過或僅預期 WARN
- [x] 7.4 確認 R-22 對本批 doc 無新懸空

## 8. 驗證與 release

- [x] 8.1 `python3 -m pytest -q` 全綠
- [x] 8.2 `python3 -m policy_check --repo .` 無 failure
- [x] 8.3 PR：zh-tw、`Closes #` 連結（如為本案開 issue）、checklist 全勾
- [x] 8.4 merge 當下 PATCH release bump（`flat`，一個 feature batch）
