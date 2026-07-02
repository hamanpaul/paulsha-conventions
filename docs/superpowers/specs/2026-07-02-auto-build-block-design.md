# Design: `.paul-project.yml` 擴充 `auto_build` 區塊（issue #30 提案 A）

- 日期：2026-07-02
- 來源：issue #30（feat: `.paul-project.yml` 擴充 build-flow 區塊 + project-scan 注入機制）
- 範圍：**僅提案 A**（本 repo 引擎 + docs）。提案 B（project-scan 注入機制）之產物落在
  custom-skills / `~/.paul-scans/`，不在本 repo，拆為後續子專案（見文末「提案 B 備忘」）。
- 決策模式：使用者暫離，依 issue 內傾向與 repo 既有慣例採 best judgment 定案；
  所有決策點列於本文件，均可翻案。

## 問題

`.paul-project.yml` 目前只承載 policy 設定。issue #30 希望它同時承載 per-project 的
build flow 定義，供 **LLM auto build**（agent 自動建置）讀取——一份 repo 內、
機器可讀、有慣例欄位的「怎麼 build 這個專案」宣告。

## 決策 1：命名 `auto_build:`（捨 `x-build:`）

issue 待決事項第 1 項。選 `auto_build`，理由：

- `.paul-project.yml` 本就是 **project** config（檔名即證據），非純 policy 檔；
  承載 build 資訊不算越界。
- repo 既有慣例：**宣告的區塊都是 engine 已知 key 並在 R-08 驗證**
  （`secret_scan` / `doc_reference` / `agent_files` / `conventions_engine` /
  `doc_paths` / `doc_coverage` / `generated_facts` / `moc`）。`auto_build` 比照。
- `x-` 前綴要防的「與未來 policy reserved key 撞名」問題，在它成為已知 key 的當下即消失。
- 對 LLM 讀者自述性更好：`auto_build:` 冷讀即知用途；`x-build:` 需要先知道擴充慣例。

**Considered & dropped**：
- `x-build:` + 在 R-08 文件化「`x-*` 永不保留」——頂層寬鬆白名單（未知 key 一律放行）
  本身就是第三方擴充的 escape hatch，再造一個正式 `x-*` 保留區是 YAGNI。
- `build:`——太泛，且不自述「給自動化/LLM 用」的意圖。

## 決策 2：驗證層級 A2-lenient（R-08 optional 驗證，未知 subkey 放行）

issue 待決事項第 2 項（A1 純 YAML vs A2 加 R-08 驗證）。選 **A2 的寬鬆版**：

- `auto_build` 若存在，須為 mapping（仿 `secret_scan`/`moc` 的 `is not None` optional pattern）。
- 已知 subkey 做型別檢查：
  - `description`: str —— 一句話說明「build 這個 repo 是什麼意思」
  - `setup`: list[str] —— 環境準備命令（toolchain、docker pull …）
  - `steps`: list[str] —— 建置命令，依序執行
  - `artifacts`: list[str] —— 產物路徑 glob
  - `verify`: list[str] —— 建置成功的驗證命令
- **未知 subkey 一律放行**：per-project 可自由加欄位；慣例欄位日後擴充
  不需要 engine release（issue 註明 build flow 初期會改，之後幾乎不變——
  演進成本壓在「不必 bump engine」這一側）。
- **無必填 subkey**：R-08 是形狀檢查器，不是語意 gate；空 mapping PASS，
  與其他 optional 區塊行為一致。
- **顯式 null subkey 視同未宣告**（codex 覆審後明確化）：`steps:` 後無值＝略過型別檢查，
  與 `secret_scan.markers:` null 等既有區塊語意一致；收緊成 key-presence 檢查反而會讓
  `auto_build` 比其他區塊更嚴，破壞一致性。已有測試釘住。

理由：型別檢查抓得住最常見的手誤（str 寫成 list、list 寫成 str），
成本只是 R-08 一段 ~30 行；A1 的「打錯字引擎不提醒」缺點確實存在，
而 A2 全嚴格版會讓每次欄位演進都綁 engine release（R-23 lockstep 下游代價高），
寬鬆版兩者兼顧。

## 界線：engine 永不執行 `auto_build` 命令

`auto_build` 的消費者是 LLM auto build agent，**不是 policy engine**。
R-08 只驗形狀；`setup`/`steps`/`verify` 內的命令字串對 engine 而言是純資料。
這與 R-16（`cli`）、R-25（`cli_tree`）、R-26（`generated_facts`）等
「命令執行型規則」明確區隔——README 的安全注意段落不因本區塊擴大執行面。

## Schema 範例

```yaml
# .paul-project.yml（節錄；全部欄位 optional，不用 build 的 repo 整塊不寫）
auto_build:
  description: "router firmware image via docker build container"
  setup:
    - "docker pull registry.example/fw-builder:latest"
  steps:
    - "docker run --rm -v $PWD:/src fw-builder make -C /src image"
  artifacts:
    - "out/*.img"
  verify:
    - "test -s out/firmware.img"
```

## 變更清單

1. `policy_check/rules/r08_policy_config_schema.py`
   —— 新增 `auto_build` 驗證段（仿 `moc` 段落結構與訊息措辭）。
2. `tests/test_rule_r08_policy_config_schema.py`
   —— 新增測試（TDD RED 先行）：
   - FAIL：`auto_build` 非 mapping（`auto_build: yes` / 字串）
   - FAIL：`auto_build.steps` 非 list[str]（字串、混型 list）
   - FAIL：`auto_build.description` 非 str
   - PASS：完整合法區塊
   - PASS：空 mapping、只寫部分欄位
   - PASS：含未知 subkey（向前相容證據）
   - PASS：未宣告 `auto_build`（回歸）
3. `README.md`
   —— 「文件規則設定面」之後新增「auto_build 區塊（LLM auto build 慣例）」段：
   schema、範例、「engine 只驗形狀、永不執行」界線（R-18 docs 同步）。
4. `changelog.d/30-auto-build-block.md` —— `type: feat`。
5. 本 repo 的 `.paul-project.yml` **不加** `auto_build`（無 build，dogfood 零負擔敘事）。
6. `policy_check/config.py` **不動**：engine 不消費 `auto_build`，不需 default。

## 測試與驗收

- `python3 -m pytest -q` 全綠。
- `python3 -m policy_check --repo .` 無 failure。
- PR 引用 issue：**不能 `Closes #30`**（提案 B 未完），PR body 寫「屬 #30 提案 A」
  並上 `policy-exempt:issue-link` label + 理由（R-17）。

## 提案 B 備忘（不在本次範圍）

中央 `~/.paul-scans/<project>/` 維護 canonical `.paul-project.yml`（含 `auto_build`）
+ `CLAUDE.md`，symlink 注入不引 conventions 的 GitLab 專案，檔名寫 `.git/info/exclude`
（local-only）。傾向：包成 skill（暫名 `project-scan`，落 custom-skills）；
平台策略 symlink（Linux/WSL）→ 實體複製 fallback（Windows；junction 對 git 語意較混沌）。
**實作前需使用者拍板**：skill vs PoC、目標專案清單、中央目錄版控與同步策略。
注意：B 定案後，`auto_build` 即為注入檔案的一部分，兩案共用本 schema。
