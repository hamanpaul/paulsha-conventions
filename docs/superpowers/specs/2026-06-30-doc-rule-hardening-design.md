# 設計：#26 文件規則補強與 doc-alignment 分層治理

> 日期：2026-06-30
> 狀態：approved（使用者已逐段拍板）
> 對應 issue：#26（docs 規則攔不到語意/範圍 drift）
> 範圍：`paulsha-conventions` 規則引擎與其設定模型
> 版本策略：本設計先定義結構，不在 spec 階段固定版本號；實作完成後依 `flat` profile 以單一 feature batch 做 PATCH bump。

## 1. 背景與目標

`serialwrap` 的文件對齊稽核暴露出一個明顯缺口：現行引擎會在 docs 已 drift 的情況下
仍然 PASS。根因不是某條規則寫錯，而是**不同性質的 drift 被混在同一個「docs 有沒有更新」概念裡**。

目前：

- `R-18` 只看「code 變了，但 `README.md` / `docs/**` 有沒有跟著變」。
- `R-22` 只看 `README.md` / `docs/**` 裡的懸空引用。
- `R-16` 只同步 CLI help marker。

因此漏掉三類問題：

1. **範圍盲區**：`CLAUDE.md`、repo root 以外的 canonical docs、skill docs 不在範圍內。
2. **omission**：新增模組 / RPC / env / CLI 子命令，文件完全沒提到。
3. **structured fact drift**：文件有列出清單，但內容過時。

本設計的目標不是讓引擎「理解散文語意」，而是把可機械化的 doc drift 分解成幾個
**單一責任、可重現、可配置**的檢查層，讓 deterministic gate 能抓住大部分高價值案例，
同時把純語意判斷明確留在 advisory 層。

## 2. 核心原則

### 2.1 確定性 gate 與 advisory semantic review 分工

`policy_check` 的 blocking rules 必須維持可重現：同一份 repo、同一份 config、同一份 PR
脈絡，結果就必須一致。因此：

- **可做成 deterministic invariant 的東西**（範圍、coverage、marker sync）進 engine。
- **需要語意理解的東西**（散文是否已經不正確）不進 blocking gate，只保留 advisory 入口。

本設計接受一個明確邊界：引擎**不讀懂文字**，只驗證 repo 宣告過的結構化事實與文件不變量。

### 2.2 單一責任，不把既有規則硬塞成萬用規則

`R-18`、`R-22`、`R-16` 已各自回答不同問題：

- `R-18`：這次 code change 有沒有碰文件。
- `R-22`：文件引用的路徑 / symbol 有沒有懸空。
- `R-16`：特定 marker block 是否與實際輸出一致。

因此 #26 不應把所有能力塞進其中一條規則，而應在保留既有職責的前提下，新增缺少的層。

## 3. 分層架構

### 3.1 Scope layer：補強現有 `R-18` / `R-22`

新增 top-level `doc_paths: list[str]`，作為 repo 宣告的 canonical docs 範圍。

- 預設值：`["README.md", "docs/**"]`
- 作用：
  - `R-18` 以 `doc_paths` 判斷「有沒有 docs change」
  - `R-22` 以 `doc_paths` 決定候選文件，再套用既有 spec / fixture 內建排除，避免行為回歸

這一層只回答「哪些檔案算 docs」，不負責 coverage、內容完整性或語意正確性。

### 3.2 Coverage layer：新增 omission rule

新增一條 coverage rule，檢查 repo 宣告的 public facts 是否至少在某個 target doc 被提及一次。

這一層只回答：

> 新增了 X，是否至少在某個 canonical doc 被 mention？

第一版支持 issue 內點名的四類事實來源：

- `modules`
- `rpc_methods`
- `env_vars`
- `cli_tree`

extractor 的共同輸出是 fact name 集合；rule 本身不關心來源是 Python 掃描、regex 擷取或
CLI 樹生成，只看「抽出了哪些 fact」以及「哪些 doc 應該覆蓋它們」。

### 3.3 Generated-fact sync layer：一般化 `R-16` 模式

把 `R-16` 背後的 marker-sync 概念抽象成通用 generated-fact 機制：

- generator 產生結構化事實的文件化表示
- doc 內有對應 marker block
- rule 比對 marker block 內容與 generator 輸出是否一致

CLI help 只是其中一種 generated fact；未來模組清單、RPC method 清單、env 清單、CLI 命令樹
都可以走同一模式。

### 3.4 Advisory semantic layer：明確不進 blocking gate

純散文正確性（例如一句設計描述語意上是否過時）不進 `policy_check` 的 deterministic gate。
它只保留為：

- 獨立 command
- nightly / optional workflow
- 或 PR review checklist / LLM reviewer 流程

這層可以被設計，但不應和 blocking rules 混在一起。

## 4. Config 模型

### 4.1 `doc_paths`

```yaml
doc_paths:
  - "README.md"
  - "docs/**"
  - "CLAUDE.md"
  - "sw_core/assets/skill/SKILL.md"
```

- 型別：`list[str]`
- 預設：`["README.md", "docs/**"]`
- 用途：提供 `R-18` / `R-22` 共用的 docs 範圍

### 4.2 `doc_coverage`

```yaml
doc_coverage:
  mode: "changed"
  targets:
    - "README.md"
    - "CLAUDE.md"
  sources:
    - kind: "modules"
      include: ["sw_core/**/*.py"]
      exclude: ["**/__init__.py", "**/tests/**"]
    - kind: "rpc_methods"
      include: ["sw_core/service.py"]
      pattern: 'method\\s*==\\s*"([^"]+)"'
    - kind: "env_vars"
      include: ["sw_core/**/*.py"]
      prefix: "SERIALWRAP_"
    - kind: "cli_tree"
      command: "python3 scripts/list-cli-paths.py"
```

設計原則：

- `mode` v1 支援 `changed` 與 `all`；**預設為 `changed`**。
- `changed` 模式以 `base...HEAD` 比較 fact 集合，只要求**本次新增**的 facts 被 mention。
- 若 `changed` 模式下無法解析 base（例如本地 `--repo .`、無 PR 脈絡），rule 降為 `WARN` 並不做 FAIL 判定。
- `targets` 必須解析到 `doc_paths` 內的 in-scope docs；若 target 超出 canonical docs 範圍，視為 config 錯誤。
- `targets` 定義哪些 docs 要參與 mention coverage。
- `sources` 是 extractor 宣告；每個 extractor 產出 fact name 集合。
- 一條 coverage rule 的核心邏輯保持固定，repo 差異只落在 extractor config。

#### 4.2.1 v1 extractor contract

| kind | 必填欄位 | 抽取方式 | fact identity |
|---|---|---|---|
| `modules` | `include`, optional `exclude` | 列舉 git-tracked 檔案，套 include/exclude glob | repo-relative POSIX 路徑，例如 `sw_core/multi_open.py` |
| `rpc_methods` | `include`, `pattern` | 對匹配檔案做 regex 掃描；`pattern` 必須恰有一個 capture group | capture group 文字，例如 `session.renumber` |
| `env_vars` | `include`, `prefix` | 掃描匹配檔案中符合 `PREFIX[A-Z0-9_]+` 的 token | 精確 env 變數名，例如 `SERIALWRAP_SOCKET_PATH` |
| `cli_tree` | `command` | 執行指令，將 stdout 視為一行一個 fact | 完整命令路徑，例如 `serialwrap session renumber` |

這裡的重點是：v1 的 built-in extractors 都是**明確、可重現、可測**的資料擷取契約，而不是隱含「引擎要自己猜 repo 的 RPC/CLI 結構」。

### 4.3 `generated_facts`

```yaml
generated_facts:
  - kind: "cli_help"
    command: "python3 -m policy_check"
    help_args: ["--help"]
    reflected_in: "README.md"
    marker: "policy-check-help"
  - kind: "fact_list"
    command: "python3 scripts/render-rpc-facts.py"
    reflected_in: "CLAUDE.md"
    marker: "rpc-methods"
```

設計原則：

- `generated_facts` 是通用 marker-sync 宣告。
- marker 語法統一為：
  ```md
  <!-- BEGIN: generated-fact marker="rpc-methods" -->
  ...
  <!-- END: generated-fact marker="rpc-methods" -->
  ```
- 執行模型固定為：`shlex.split`、**不經 shell**、`cwd=repo_root`、`LC_ALL=C`、固定 timeout 30 秒。
- generic generated facts 只比較**正規化 UTF-8 stdout**；stderr 非空不參與比對，command non-zero exit 直接 `FAIL`。
- 既有 `cli` 區塊在第一版保留相容；`R-16` 可先沿用既有入口，底層 helper 再抽共用。
- 既有 `cli-help` marker 與 `R-16` 維持 backward-compatible；generic marker-sync 不強迫舊 repo 立即改 marker。
- 第二步才考慮是否讓 `cli` 成為 `generated_facts` 的語法糖。

### 4.4 為何不把設定塞進 `doc_reference`

三者責任不同：

- `doc_paths` = docs 範圍
- `doc_coverage` = omission coverage
- `generated_facts` = structured fact sync

把它們拆開可以讓 schema 更清楚、錯誤訊息更精準，也避免 `R-22` 的 config 概念膨脹。

## 5. Rule 行為邊界

### 5.1 `R-18`

- 保持 advisory `WARN` 性質不變。
- 唯一核心變更：docs 範圍從硬編碼改讀 `doc_paths`。
- 若 repo 未宣告 `doc_paths`，使用預設值，維持現行行為。

### 5.2 `R-22`

- 保持現有 diff-aware dangling reference 機制。
- 唯一核心變更：掃描範圍改讀 `doc_paths`，但仍保留既有 `openspec/**`、`docs/superpowers/**`、fixture tree 的內建排除。
- 它仍然只負責**引用完整性**，不負責 coverage 或 semantic correctness。

### 5.3 Coverage rule

coverage rule 為新 rule，不併入 `R-18` 或 `R-22`。

若 repo **未宣告** `doc_coverage`，rule 視為 not-applicable，直接 `PASS`。

若 repo 宣告了 `doc_coverage`，則：

- `mode: changed`：只檢查 `base...HEAD` 新增的 facts
- `mode: all`：檢查 extractor 產出的全部 facts
- fact 至少在某個 target doc 被 mention → `PASS`
- fact 完全未被 target docs mention → `FAIL`
- config 缺失、extractor 參數無效、target doc 不存在 → `FAIL`

為了避免實作歧義，v1 明確固定 mention 判定：

- `modules`：fact 名稱為 repo-relative 路徑，例如 `sw_core/multi_open.py`
- `rpc_methods`：fact 名稱為 method 字串本身，例如 `session.renumber`
- `env_vars`：fact 名稱為環境變數名，例如 `SERIALWRAP_SOCKET_PATH`
- `cli_tree`：fact 名稱為完整命令路徑，例如 `serialwrap session renumber`
- mention 規則採**區分大小寫的精確 token / phrase 比對**；只算完整名稱命中，不接受較長字串中的子字串誤算。

這樣 omission 才會成為真正的 deterministic gate，而不是 advisory 提醒。

### 5.4 Generated-fact sync

generated-fact sync 採 FAIL-fast：

- repo **未宣告** `generated_facts` → rule 視為 not-applicable，直接 `PASS`
- repo 宣告了 `generated_facts` 但 config 不完整或格式錯誤 → `FAIL`
- marker block 與 generator 輸出一致 → `PASS`
- marker 缺失、指令無法執行、輸出不一致 → `FAIL`

第一版保留 `R-16` 的相容介面，只抽共用 helper，不強迫所有 repo 立即重寫 config。

### 5.5 Advisory semantic layer

不進 blocking rules 主體，不影響 `policy_check` exit code。

若未來實作，應被視為獨立流程，其輸出性質應是：

- advisory only
- 可明確標示非 deterministic
- 不與 pinned-SHA 的 blocking contract 混在一起

## 6. 元件與資料流

| 元件 | 做什麼 | 輸入 | 輸出 |
|---|---|---|---|
| `doc_paths` | 宣告 canonical docs 範圍 | glob 清單 | `R-18` / `R-22` 使用的 in-scope doc 集合 |
| `R-18` | 檢查 code change 是否有 docs touch | `changed_files`, `doc_paths` | `PASS/WARN/SKIP` |
| `R-22` | 檢查 in-scope docs 的 dangling reference | `doc_paths`, repo snapshot, diff context | `PASS/WARN/FAIL/SKIP` |
| coverage rule | 檢查 fact omission | `doc_coverage.mode`, `sources`, `targets`, diff context | `PASS/WARN/FAIL` |
| generated-fact sync | 檢查 marker block 是否同步 | `generated_facts` | `PASS/FAIL` |
| advisory semantic audit | 額外語意稽核 | docs + code + reviewer/LLM | advisory result |

資料流順序上，coverage 與 generated-fact sync 都是建立在 repo 已經明確宣告範圍與事實來源之上，
而不是從全 repo 任意猜測「哪些檔案可能重要」。

## 7. 測試策略

### 7.1 config/schema

- `doc_paths` 預設值與型別驗證
- `doc_coverage` mapping 結構驗證
- `generated_facts` list/object 結構驗證
- `mode` 僅允許 `changed` / `all`

### 7.2 `R-18` / `R-22` regression

- `README.md` / `docs/**` 現有案例不退化
- 加入 `CLAUDE.md`、自訂 skill doc 等新範圍案例
- 未宣告 `doc_paths` 時行為與今天一致

### 7.3 Coverage rule

- fact 被 mention → `PASS`
- fact 漏記 → `FAIL`
- `mode: changed` 只對新增 facts 生效
- `mode: changed` 且 base 不可解析 → `WARN`
- extractor config 壞掉 → `FAIL`
- target doc 不存在 → `FAIL`
- token / phrase boundary 案例固定：完整命中才算，子字串誤中不算

### 7.4 Generated-fact sync

- marker 與實際輸出一致 → `PASS`
- marker 缺失 → `FAIL`
- 輸出不一致 → `FAIL`
- 與既有 `R-16` 並存時不互相踩到

## 8. 相容性與 rollout

### 8.1 相容性原則

- **未宣告新 config 的 repo**：維持既有行為，不因 #26 突然被新 gate 打爆。
- **`doc_paths`**：屬低風險預設擴充，應自動有 sane default。
- **`doc_coverage` / `generated_facts`**：採 opt-in；未宣告時 rule not-applicable 直接 `PASS`，只有宣告後才受其 gate 約束。

### 8.2 rollout 順序

1. Phase 1：加入 `doc_paths`，補強 `R-18` / `R-22`
2. Phase 2：新增 coverage rule，先支援少數 extractor
3. Phase 3：抽出 generated-fact sync helper，擴展到非 CLI 事實
4. Phase 4：定義 advisory semantic audit 介面或工作流

這個順序的目的，是先補掉當下最明確的範圍盲區，再逐步把 omission 與 stale structured facts
收進 deterministic gate。

## 9. 預期實作面

- `policy_check/config.py`
- `policy_check/rules/r08_policy_config_schema.py`
- `policy_check/rules/r18_docs_sync.py`
- `policy_check/rules/r22_doc_reference.py`
- 新增 coverage rule 與對應測試
- 抽出或共用 generated-fact / marker-sync helper
- `tests/test_rule_r18_docs_sync.py`
- `tests/test_rule_r22_doc_reference.py`
- 新增 coverage / generated-fact 測試
- `README.md`
- `CHANGELOG.md`
- `.paul-project.yml`（dogfood 新 config）

## 10. Non-goals

- 不把「散文是否正確」做成 blocking gate
- 不要求 coverage rule 從全 repo 自動猜測所有 public facts
- 不在第一版就統一取代 `R-16` 的現有 `cli` config 入口
- 不把所有語言的 symbol / API 抽取一次做到齊全

## 11. 決策摘要

本設計把 #26 定位成：

1. **補強現有 rule**：用 `doc_paths` 修正 `R-18` / `R-22` 的 docs 範圍盲區
2. **新增 deterministic omission gate**：用 coverage rule 抓「新增了 X 卻沒記」
3. **一般化 structured-fact sync**：把 `R-16` 的 marker 模式擴展成通用機制
4. **明確分離 advisory semantic review**：承認純語意正確性不屬 blocking engine

這樣既保留現有 rule 的可理解性，也把 issue #26 的真正價值——從「文件有沒有碰」提升到
「文件是否覆蓋了 repo 宣告的重要事實」——拆成可以逐步落地的 deterministic primitives。
