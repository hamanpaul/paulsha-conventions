# auto-build-config Specification

## Purpose
定義 `.paul-project.yml` 的 optional `auto_build:` 區塊：per-project build flow 的機器可讀慣例
（消費者為 LLM auto build agent），及 R-08 對該區塊的 lenient 形狀驗證與「engine 永不執行」邊界。
（issue #30 提案 A；archived change: auto-build-block）

## Requirements

### Requirement: auto_build 區塊為 optional 且未宣告時行為不變
`.paul-project.yml` 的 `auto_build` 頂層區塊 SHALL 為 optional：未宣告該區塊的 repo，
R-08 及所有既有規則的行為 MUST 與本 capability 引入前完全相同。

#### Scenario: 未宣告 auto_build
- **WHEN** `.paul-project.yml` 合法且不含 `auto_build` key
- **THEN** R-08 回報 PASS，訊息與既有行為一致

#### Scenario: 空 mapping
- **WHEN** `.paul-project.yml` 宣告 `auto_build: {}`（或等價空 mapping）
- **THEN** R-08 回報 PASS

#### Scenario: bare key（YAML null）視同未宣告
- **WHEN** `.paul-project.yml` 只寫 `auto_build:` 而無內容（YAML 值為 null）
- **THEN** R-08 回報 PASS（與未宣告同義，與其他 optional 區塊一致）

### Requirement: auto_build 必須是 mapping
若 `auto_build` 存在，其值 SHALL 為 YAML mapping；否則 R-08 MUST 回報 FAIL，
訊息含 `auto_build must be a mapping`。

#### Scenario: 整塊寫成字串
- **WHEN** `.paul-project.yml` 宣告 `auto_build: make image`
- **THEN** R-08 回報 FAIL，訊息含 `auto_build must be a mapping`

### Requirement: 已知 subkey 型別驗證
R-08 SHALL 對 `auto_build` 的已知 subkey 做型別檢查：`description` MUST 為 str；
`setup`、`steps`、`artifacts`、`verify` MUST 各為 list[str]（空 list 合法）。
違反者 R-08 MUST 回報 FAIL，訊息含 `auto_build.<subkey>`。所有 subkey 皆非必填。

#### Scenario: steps 寫成字串
- **WHEN** `auto_build.steps` 的值為 `"make image"`（str 而非 list）
- **THEN** R-08 回報 FAIL，訊息含 `auto_build.steps`

#### Scenario: steps 為混型 list
- **WHEN** `auto_build.steps` 為 `["make", 42]`
- **THEN** R-08 回報 FAIL，訊息含 `auto_build.steps`

#### Scenario: description 寫成 list
- **WHEN** `auto_build.description` 的值為 list
- **THEN** R-08 回報 FAIL，訊息含 `auto_build.description`

#### Scenario: 完整合法區塊
- **WHEN** `auto_build` 含 `description`（str）與 `setup`/`steps`/`artifacts`/`verify`（皆 list[str]）
- **THEN** R-08 回報 PASS

#### Scenario: 只寫部分欄位
- **WHEN** `auto_build` 只含 `steps: ["make"]`
- **THEN** R-08 回報 PASS

### Requirement: 未知 subkey 放行
R-08 SHALL 忽略 `auto_build` 內未知 subkey（不驗證、不 FAIL、不 WARN），
使慣例欄位之外的 per-project 擴充與日後欄位演進不需要 engine release。

#### Scenario: 含未知 subkey
- **WHEN** `auto_build` 含 `steps: ["make"]` 與未知 subkey `timeout_minutes: 30`
- **THEN** R-08 回報 PASS

### Requirement: engine 永不執行 auto_build 內容
policy engine SHALL 將 `auto_build` 內所有值視為純資料：R-08 驗證過程 MUST NOT
執行（spawn subprocess）`setup`/`steps`/`verify` 中的任何命令字串。此界線 SHALL
文件化於 README 的 `auto_build` 說明段，與 R-16/R-25/R-26 命令執行型規則明確區隔。

#### Scenario: 驗證含命令的區塊無副作用
- **WHEN** `auto_build.steps` 含會產生可觀察副作用的命令（如 `touch marker-file`）且執行 R-08
- **THEN** R-08 完成驗證且該副作用不發生（marker 檔不存在）

### Requirement: 慣例欄位語意
`auto_build` 慣例欄位 SHALL 依下列語意文件化，供 LLM auto build agent 消費：
`description` 一句話說明 build 目標；`setup` 環境準備命令；`steps` 依序執行的建置命令；
`artifacts` 產物路徑 glob；`verify` 建置成功之驗證命令。

#### Scenario: LLM agent 冷讀取得 build 流程
- **WHEN** LLM agent 讀取宣告了 `auto_build` 的 `.paul-project.yml`
- **THEN** 依 `setup` → `steps` → `verify` 順序即得完整建置流程，`artifacts` 指出預期產物
