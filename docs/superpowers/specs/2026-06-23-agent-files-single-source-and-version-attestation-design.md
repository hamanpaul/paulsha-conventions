---
title: Agent 慣例檔單一真檔（symlink）＋ 版本 attestation gate
date: 2026-06-23
status: approved
profile: flat
policy_version_at_design: 1.0.5
---

# Agent 慣例檔單一真檔（symlink）＋ 版本 attestation gate

## 1. 背景與問題

本 repo（`paulsha-conventions`）是一套 **agent-first policy-as-code** 引擎：規則的 enforce-face 是確定性 CI gate，teach-face 是 agent 進場機器載入的慣例檔。現況有三個結構性問題：

1. **四檔 byte-identical 複本（anti-pattern）**：`CLAUDE.md` / `AGENTS.md` / `GEMINI.md` / `.github/copilot-instructions.md` 是四份逐位元組相同的實體檔（皆 5586 bytes、同 mtime）。每次改動須手動同步四份，R-14 僅事後驗版本一致，無法防「有人改了其中一份」。

2. **版號鏈只驗 intra-repo 自洽**：目前
   - `R-14`：agent 檔 `policy_version:` == `.paul-project.yml`。
   - `R-20`：workflow `policy_version:` 字面值 == `.paul-project.yml`。
   - `R-15`：workflow `uses:` 必須 tag/SHA pin（但**不比對 pin 的版本值**）。

   三者互相自洽，**卻沒有任何規則把它們綁到「這個 repo 實際 pin 的引擎版本」**。下游可把 `uses: …/paulsha-conventions@v1.0.5` 升上去、卻忘了把 `policy_version` 從 1.0.2 改齊，**所有規則照樣 PASS**。

3. **P0 跨 repo 漂移**：`.github` / `new-project-template` 停在 `policy_version 1.0.2`、canonical 已 `1.0.5`。引擎只看 intra-repo，結構性看不到此漂移——正是這套東西宣稱要防的事。

## 2. 目標與非目標

### 目標
- 將 `CLAUDE.md` 立為**唯一真檔（canonical）**，其餘三檔改為 symlink，「以後只維護一份」。
- 把「單一真檔」從慣例**升級為 enforce**（divergent 複本會 FAIL），但以 config gate 漸進、不打斷下游。
- 補上 **attestation gate**：repo 實際 pin 的引擎版本必須與宣告的 `policy_version` 對齊，閉合版號鏈。

### 非目標（明確排除，留待其他 spec）
- **cross-repo currency 硬 gate**（某 repo 版本 vs canonical 最新版）——歸 org 層漸進強制／報表，非 per-repo FAIL。
- **MOC / 專案層 stage 地圖治理**——獨立 spec（見 memory `moc-cross-stage-governance`）。
- **業界方法全面抽換稽核**（R-10→action-semantic-pull-request、R-12/SHA-pin→org rulesets、lychee…）——獨立 workstream。

## 3. 設計

### 變更 1：symlink 拓撲
canonical = `CLAUDE.md`（真檔，保留 `managed-by` 戳記與 `policy_version:` 行）。其餘三檔改為 symlink：

| 檔案 | symlink 目標 |
|---|---|
| `AGENTS.md` | `CLAUDE.md` |
| `GEMINI.md` | `CLAUDE.md` |
| `.github/copilot-instructions.md` | `../CLAUDE.md` |

ext4/WSL 下 git 以 mode 120000 記錄。Claude Code 原生讀 `CLAUDE.md`（不跟 symlink 也能讀到真內容）；讀 `AGENTS.md` 的工具跟隨 symlink 取得同一份內容。

### 變更 2：`.paul-project.yml` 新增區塊（R-08 擴充驗證）
```yaml
agent_files:
  mode: symlink          # 列舉 {symlink, copy}；預設 copy（向後相容）
conventions_engine:
  repo: hamanpaul/paulsha-conventions   # 下游設此；canonical 本 repo 可不設
```
R-08 沿用既有 `secret_scan` / `doc_reference` 的驗證風格新增：
- `agent_files`（若存在）須為 mapping；`agent_files.mode`（若存在）須 ∈ {`symlink`, `copy`}。
- `conventions_engine`（若存在）須為 mapping；`conventions_engine.repo`（若存在）須為 str。

`config.load()` 對 `agent_files.mode` 預設 `copy`（未設時行為不變）。

### 變更 3：Hardened R-14（config-gated）
R-14 由「四檔版本一致」升級為「**agent files 單一真檔完整性**」，行為依 `agent_files.mode`：

| mode | 語意 |
|---|---|
| `copy`（預設） | **維持現行**：四檔皆真檔、各自 `policy_version:` == declared；缺檔交 R-13。下游不被打斷。 |
| `symlink` | `CLAUDE.md` 須**真檔**（`is_symlink()` False）且 `policy_version:` == declared；其餘三檔須為 **symlink 且 `resolve()` == `CLAUDE.md`**。違反者列出並 FAIL（"expected symlink → CLAUDE.md"／"symlink target mismatch"／"canonical must be a regular file"）。缺檔／斷鏈交 R-13（`is_file()` 對斷鏈回 False）。 |

`mode: symlink` 下三 symlink 已 resolve 到 canonical，內容/版本必然同一，不需再各讀版本。R-14 維持 `exempt_label = None`（版號真相不可豁免）。

### 變更 4：新增 R-23「engine pin ⟷ policy_version attestation」
- **適用判斷**：掃 `.github/workflows/*.yml` 中 `uses:` 指向 `conventions_engine.repo` 的行。`./` 在地引用一律跳過（canonical 本 repo 因 `uses: ./...` → 無外部 pin → NA）。`conventions_engine.repo` 未設或查無外部 pin → NA（PASS，附說明）。
- **取版本**：
  - tag ref `@vX.Y.Z` → 版本 = `X.Y.Z`。
  - SHA ref `@<40hex>` + 同行尾註 `# vX.Y.Z` → 版本取自註解。
  - 純 SHA 無版本註解 → 無法離線驗證 → **WARN**（建議補 `# vX.Y.Z` 註解）。
- **比對**：取得的版本 ≠ `ctx.policy_version` → **FAIL**（"engine pinned at vA but policy_version declares B; align on upgrade"）；相等 → PASS。
- **豁免**：新增白名單 label `policy-exempt:engine-pin`。

> 設計張力（記錄於文件）：筆記 §5 建議 SHA-pin 委派 L0（資安）。純 SHA 無法離線反推版本，故 attestation 對純 SHA 僅能 WARN；要 FAIL-grade 對齊，pin 行需帶 `# vX.Y.Z` 註解。此註解即 SHA-pin 與版本宣告之間的 attestation 橋樑（與 dependabot 慣例一致）。

### 版號鏈閉合
```
uses:@ref 引擎版本 ──R-23──▶ policy_version ──R-14──▶ agent 檔（symlink 下字面同一）
                                    └──────R-20──────▶ workflow policy_version 字面值
```
下游「升級引擎卻忘改版號」（或反之）會被 R-23 擋下。

### 變更 5：慣例檔文字、白名單、文件、程序
- `CLAUDE.md`：
  - 第 2 行 header 註記「同步更新…四份」→ 改述 symlink 單一真檔模型。
  - 第 36 行 release checklist「四份 agent 檔」用語 → 「canonical `CLAUDE.md`（其餘 symlink 自動跟隨）」。
  - 第 63 行「禁止：修改本檔而不同步其他三份」→ 「禁止：把 agent symlink 還原成獨立複本」。
  - Exemption 白名單新增 `policy-exempt:engine-pin` — R-23。
  - Rule 目錄／checklist 補 R-23。
- `README.md` / `docs/**`：同步四檔模型、R-14 新語意、R-23 新規則（R-18／R-22）。
- `CHANGELOG.md [Unreleased]`：補本批 entry。

## 4. fleet-safety 與跨平台
- `mode` 預設 `copy` → 下游（pin 舊引擎 SHA 的 `.github` / `new-project-template`）bump 後行為不變，可各自排程遷移。
- CI 為 GitHub Actions ubuntu，`actions/checkout` 在 Linux 保留 symlink → R-14 symlink 模式在 CI 正常。
- `tier: shareable`：於無 symlink 支援的平台 clone，三 symlink 會退化為內含路徑字串的純文字檔。**接受並於 README/spec 註記**；不建生成器（違背「只維護一份」初衷）。主開發環境為 WSL/ext4，下游消費的是引擎而非這幾份慣例檔。

## 5. 測試計畫（TDD，全走 fixture）
- **R-14**：`copy` 模式正例（四真檔版本齊）/ 負例（版本 drift→FAIL）；`symlink` 模式正例（三 symlink→CLAUDE.md→PASS）/ 負例（其一為複本→FAIL、其一指向錯誤→FAIL、canonical 為 symlink→FAIL）。
- **R-08**：`agent_files.mode` 非法值→FAIL、合法→PASS；`conventions_engine.repo` 非 str→FAIL。
- **R-23**：tag 對齊→PASS / 不齊→FAIL；SHA+`# vX.Y.Z` 對齊→PASS / 不齊→FAIL；純 SHA 無註解→WARN；`./` 在地→NA；`conventions_engine` 未設→NA。
- **dogfood**：本 repo 設 `agent_files.mode: symlink`，實跑 `policy_check` R-13/R-14 仍 PASS、R-23 NA。

## 6. policy / 程序
- 分支：`feature/agent-files-single-source-attestation`（已開）。
- 改 engine（`policy_check/**`）⇒ `CHANGELOG [Unreleased]` 必填。
- merge 當下立即 release bump `1.0.5 → 1.0.6`：`VERSION` / `.paul-project.yml policy_version` / `CLAUDE.md`（含 `managed-by@v1.0.6`）/ workflow `policy_version` 字面值 / tag / `RELEASES.md`。
- 語言：PR 標題／內文／comment 一律 zh-tw（本 repo 屬 hamanpaul）。
- 完成前：pytest 全綠、`python3 -m policy_check --repo .` 無 failure、PR template checklist 全勾。

## 7. 風險與待解
- **R-23 對純 SHA 僅 WARN**：實際下游若全用無註解 SHA pin，attestation 短期只能 advisory；落地後應推「pin 行帶 `# vX.Y.Z`」慣例，或後續引入 SHA→version 查表（cross-repo currency 那條 spec 的範疇）。
- **新增 R-23 的目錄 churn**：白名單、README rule 目錄、presence/integration 測試需手動同步——正凸顯 MOC/self-index 缺口（另案）。
- R-23 採獨立新 rule（非擴充 R-20），保其獨立 exemption 與 WARN 語意；若日後覺得過細可再併。

## 8. 後續（明確接棒）
1. **attestation cross-repo currency**（per-repo vs canonical 最新版的報表／org 層強制）。
2. **MOC / 專案層 stage 地圖治理**（memory `moc-cross-stage-governance`）。
3. **業界方法抽換稽核**（workstream 1）。
