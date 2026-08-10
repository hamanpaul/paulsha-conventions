---
title: ISO/IEC 42001 opt-in engineering-evidence profile 設計
date: 2026-08-10
status: draft（docs-only 設計交付；schema 落地與規則實作待 follow-up issue）
profile: flat
policy_version_at_design: 1.0.15
related_issue: "#60 ISO/IEC 42001 opt-in profile 設計"
---

# ISO/IEC 42001 opt-in engineering-evidence profile 設計

> 本文件為 issue #60 的 docs-only 設計交付。本分支不改動任何 `policy_check/**` 程式碼；
> schema 落地（Stage 2）與規則實作（Stage 3）留待 §6 描述的 follow-up issue。

## 0. 範圍與免責聲明（先講在前面）

- 本文件只引用 ISO/IEC 42001:2023 的 **clause 編號**與 **Annex A control 分類編號／主題**，
  並以自撰文字描述「這條規則的 implementation intent」。**不轉錄、不改寫、不節譯標準原文
  條文**——文中不會出現任何一句可辨識為 ISO 條文原文的文字。
- 映射粒度**只到 clause（4–10）／Annex A 分類層級（A.2–A.10 的分類主題）**，不做到逐條
  sub-control（如 A.6.2.3）等級。理由：sub-control 層級的精確編號與範圍需對照正式付費文本
  才能確保不誤植，本設計未取得、也不會取得標準原文，寧可映射得粗一點、但每一格都誠實可核對。
- **最終 mapping 需以合法取得的正式 ISO/IEC 42001:2023 文本核對**——本文件的對映表是「工程
  證據可以支撐哪個分類方向」的**設計假說**，不是稽核結論。
- 本設計不代表、不宣稱、也不能讓任何 repo「符合 ISO/IEC 42001 認證」。它只提供**機械可證的
  工程證據**，回答「宣稱的治理動作有沒有實際留下痕跡」；證書化（certification）判斷永遠是
  人類稽核員依正式文本、訪談與抽樣核對後才能下的結論。

## 1. Opt-in 機制

延續本引擎既有的 opt-in 區塊慣例（`moc` / `doc_coverage` / `generated_facts`：**未宣告 →
對應規則一律 NA/PASS，既有 repo 行為零變更**，即 bounded governance 原則的既有實作模式）。

`.project-policy.yml` 新增頂層 `iso42001` 區塊，**整個區塊本身即為總開關**：

```yaml
# 全部子欄位皆選填；iso42001 區塊本身也選填。
# 未宣告 iso42001 → 本 profile 下所有 ISO-NN 規則 NA（見 §3）；
# 對現有 76 個下游 repo 是 no-op（bounded governance）。
iso42001:
  systems:                            # AI 系統盤點：single source of truth（one authority per fact）
    - id: "chat-assistant"            # repo 內唯一 id；R-08 驗證不可重複
      owner: "team-x"                 # 自由文字；機械只驗證「有填」，不判斷組織是否正確
      intended_use: "customer support triage"
      risk_tier: "limited"            # 自由文字；機械不判斷分級是否合理（physical reality wins）
      code_paths: ["src/assistant/**"]
      data_paths: ["data/assistant/**"]
  third_party_components:             # Annex A.10 方向：第三方 / 供應鏈揭露
    - name: "anthropic-claude"
      role: "foundation-model"
      version_ref: "claude-sonnet-5"
  data_provenance_doc: "docs/data/PROVENANCE.md"     # Annex A.7 方向：資料來源文件
  incidents_dir: "iso42001-incidents.d"              # Clause 10 方向：改善／不符合紀錄目錄
```

Schema 驗證比照現有 R-08 模式（Stage 2，見 §6）：R-08 只驗**形狀**（型別、必要 key、id 唯一性），
**不驗內容語意**（如 `risk_tier` 的值是否合理）——語意判斷是人類稽核員的工作，機械只負責
「宣稱的欄位有沒有規律地被填、有沒有對應的證據」。這與既有 `moc` / `doc_coverage` /
`generated_facts` 三個區塊在 R-08 中的驗證深度一致，不是新的驗證哲學。

## 2. 證據對映表

下表逐條寫「此規則能證明什麼、不能證明什麼」，並標示對映的 ISO/IEC 42001 分類方向
（clause 或 Annex A 分類編號 + 我方自撰的主題摘要，非條文原文）。

| 規則 | 對映分類方向（設計假說） | 能證明 | 不能證明 |
|---|---|---|---|
| **R-09**（code↔changelog 同步） | Clause 7.5 文件化資訊 / Annex A.6 方向：AI 系統生命週期變更留痕 | 每次 `code_paths` 命中的變更，PR 當下都有一則同時新增的 `changelog.d/*.md` 描述 | 描述內容正確、完整，或變更本身經過風險評估——只證明「有留痕」，不證明「留痕品質」（呼應 no self-certification：作者自寫的一句話不是治理判斷） |
| **R-14**（agent 慣例檔版本同步） | Annex A.3 方向：內部治理職責一致性 | 分派給 AI agent 的操作指令（CLAUDE.md/AGENTS.md/GEMINI.md/copilot-instructions.md）在同一 commit 下宣告同一 `policy_version`，不存在分岔版本 | agent 實際執行時是否真的遵循該指令內容——只證明「指令文本單一權威」，不證明「行為合規」（one authority per fact 的直接體現；行為證據要看 runtime log，屬 physical reality wins） |
| **R-15**（workflow uses pin） | Annex A.4 方向：AI 系統所依賴資源之供應鏈完整性 | CI 引用的每個 external Action 都釘死在 tag 或 40 碼 SHA，不存在可變分支 ref | 被釘住的內容本身無漏洞、無惡意；pin 只保證「這次讀到的版本不會被之後的推送悄悄替換」，不做內容審查 |
| **R-16**（CLI help 同步） | Annex A.8 方向：對外部關係人揭露之系統介面資訊正確性 | 文件中 marker 區塊內容與實際執行 `--help` 的輸出逐字元相同（點時間快照） | 文件涵蓋了系統的全部行為，或後續未再漂移——只驗「本次 check 當下」的一致性，靠每次 PR 重跑維持 |
| **R-19**（CI 有無實際跑測試） | Clause 9 績效評估 / Annex A.6 方向：驗證與確認活動留痕 | 若 `tests/` 存在測試檔，某個 CI workflow 檔內確實出現可辨識的測試執行指令字串 | 測試通過、覆蓋率足夠，或這次 PR 的 CI 真的執行成功——v1 是**靜態文字偵測**，可能被註解或安裝行誤觸發（issue #62 正在把它改為結構化 YAML 偵測，這是同一份「能證明」邊界的既有已知落差，見該 plan） |
| **R-20**（workflow policy_version 同步） | Annex A.3/A.6 方向：治理引擎版本設定一致性 | CI 消費治理引擎的 reusable workflow 呼叫端所宣告 `policy_version` 字面值，與專案宣告值一致 | 該版本號對應的引擎程式碼內容確實等於宣告版本——版本字串比對，不做內容雜湊 |
| **R-22**（doc 懸空引用） | Clause 7.5.3 文件化資訊控制 / Annex A.8 方向 | 本次變更未在 canonical doc 範圍內引入新的懸空路徑／symbol 引用（本次新破壞 FAIL、陳年 WARN） | 文中敘述仍語意正確——引用存在 ≠ 描述沒過時；語意陳舊由 CLAUDE.md 的 advisory 層（Copilot reviewer）處理，非確定性 gate |
| **R-23**（engine pin attestation） | Annex A.4/A.10 方向：治理引擎供應鏈與版本可歸責性 | 下游 repo 的 CI 實際 pin 的引擎版本（tag 或 SHA + 尾註）與其宣告的 `policy_version` 一致——把「repo 聲稱遵守的規則版本」與「CI 實際執行的程式碼版本」對上 | 該 pin 版本的引擎程式碼本身邏輯正確；也不防禦已取得推送權限者對該 tag/SHA 的竄改（信任鏈終止於 git host） |
| **R-25**（doc coverage / omission gate） | Annex A.8 方向：系統文件完整性（omission 面） | 依 repo 自訂的結構化來源（`modules`/`rpc_methods`/`env_vars`/`cli_tree`）抽出的「事實」字串，每一則都至少在目標文件出現過一次 | 該提及的說明品質、正確性或上下文是否恰當——只做 substring/token 存在性比對 |
| **R-26**（generated-fact marker 同步） | Annex A.8 方向（同 R-16，泛化到任意結構化生成事實） | marker 區塊內容與宣告命令的 stdout 逐字元相同 | 同 R-16：只保證「本次 check 當下」一致，不保證涵蓋完整或未來不漂移 |

## 3. 新規則規劃

先盤點既有規則覆蓋不到的證據需求。§2 的十條規則共通的能力邊界是：**它們都只認得
「泛用的軟體工程產物」（changelog、doc、CI workflow、CLI help）**，認不出「這件事跟哪個
declared 的 AI 系統有關」「誰以非作者身分核准了它」「資料流向文件有沒有同步更新」
「AI-specific 事件有沒有留下改善紀錄」。這四類缺口對映到 §1 schema 的四個區塊。

依「先查能否重用既有機制」原則，先決定**哪些缺口只需擴充既有規則，哪些才真的需要新
命名空間**：

### 3.1 可重用既有機制、不佔用新 rule_id

- **第三方元件揭露同步**：`iso42001.third_party_components[].name` 逐一出現在指定揭露文件——
  這正是 **R-25（doc_coverage）** 已有的「宣告事實來源 + 比對目標文件」形狀。目前
  `policy_check/rules/_fact_extract.py` 的四種 `kind`（`modules`/`rpc_methods`/`env_vars`/
  `cli_tree`）都是「掃檔案／跑指令」，沒有「讀 `.project-policy.yml` 自身某個 list 欄位」
  的 extractor kind。**規劃**：Stage 3 為 `_fact_extract.py` 新增一個 `config_list` kind
  （`path: "iso42001.third_party_components[].name"` 這類簡單 dotted-path 讀法），讓
  repo 用既有 R-25 配置就能做到「宣告的第三方元件都在文件裡揭露」，不新開 rule_id。

### 3.2 需要新命名空間 `ISO-NN` 的規則

以下缺口是「跟 declared AI 系統的關聯性」或「既有 `RuleContext` 拿不到的資料」，既有規則
的形狀套不上，規劃獨立編號（`ISO-01` 起，不佔用 `R-NN`）：

#### ISO-01 — AI 系統變更關聯性（system impact linkage）

- **缺口**：R-09 只證明「有 changelog fragment」，證明不了「這則 fragment 是在講哪個
  declared AI 系統」。跨系統盤點需要的是可機械追溯的**關聯**，不只是泛用留痕。
- **Evidence schema 草案**：當 `ctx.changed_files` 命中某個 `iso42001.systems[].code_paths`
  時，本次新增／修改的 changelog fragment frontmatter 須含 `iso42001_system: <id>`（`id`
  須存在於 `iso42001.systems[]`）。
- **Fail/Warn 語意**：命中 code_paths 但找不到任何 fragment 帶對應 `iso42001_system` → FAIL。
  未宣告 `iso42001.systems` → NA（PASS）。豁免 label 比照既有慣例另訂
  （非 §CLAUDE.md 白名單既有項目，需在 follow-up issue 中一併提案新增）。

#### ISO-02 — 非自證人工核准（no-self-certification attestation）

- **缺口**：這是六原則中「no self-certification」最直接的機械化落點，但**目前
  `RuleContext`（`policy_check/rules/base.py`）不帶 PR review／approval 資料**，只有
  `pr_title`/`pr_body`/`pr_labels`/`pr_base_ref`/`pr_head_ref`。GitHub 的 review/approval
  清單不在 PR-opened webhook payload 裡，需額外呼叫 GitHub REST API（`GET
  /repos/{owner}/{repo}/pulls/{n}/reviews`）。**這是本規劃中唯一需要擴充 `RuleContext`
  本體（新增如 `pr_approvals: list[dict]` 欄位）與 CI 呼叫面的規則**，實作成本明顯高於
  其他 ISO-NN 項目，需在 follow-up issue 中獨立排期。
  GitLab 對等資料源是 merge request approvals API，CI 環境變數不提供，需求同樣成立。
- **Evidence schema 草案**：命中 `iso42001.systems[].code_paths` 或 `data_paths` 的 PR，
  須存在至少一則來自非作者帳號的 approve review。
  **不可離線判定**——CI（含 GitHub token 的環境）才拿得到 review 資料，本機 `policy_check
  --repo .` 跑不出這條的確定結果。
- **Fail/Warn 語意**：review 資料不可得（本機、或 token 權限不足）→ WARN（訊息明講「未取得
  review 資料，此規則需 CI 環境」），不可在證據缺失時 FAIL-blind；資料可得且只有作者本人
  approve（或無 approve）→ FAIL；資料可得且有非作者 approve → PASS。

#### ISO-03 — 資料來源文件連動（data provenance linkage）

- **缺口**：Annex A.7 方向的「AI 系統所用資料」文件化，現有規則裡最接近的是 R-18
  （`docs_sync`，advisory WARN、只看「PR 有無同時碰 docs」），但 R-18 不特定針對資料流。
- **Evidence schema 草案**：`ctx.changed_files` 命中任一 `iso42001.systems[].data_paths`
  時，本次變更須同時觸及 `iso42001.data_provenance_doc` 指定的文件（比照 R-09
  的「code_paths 命中 → 需要對應留痕」形狀，但目標從 changelog fragment 換成宣告的
  provenance 文件路徑）。
- **Fail/Warn 語意**：命中 data_paths 但 provenance 文件未在同一 diff 中變更 → FAIL；
  未宣告 `data_paths` 或 `data_provenance_doc` → NA（PASS）。

#### ISO-04 — AI 事件／不符合紀錄（incident fragment）

- **缺口**：Clause 10「改善」方向目前完全沒有對映規則；既有 changelog.d fragment 機制
  已證明「per-PR 獨立檔案、release 時彙整」這個形狀好用，直接沿用到獨立目錄。
- **Evidence schema 草案**：重用 R-09 的 `_pr_added_fragment` 邏輯，換掃描前綴為
  `iso42001.incidents_dir`（預設不啟用；宣告後才生效）。當 PR 帶特定 label（沿用
  CLAUDE.md 既有豁免 label 命名慣例，另訂如 `ai-incident`，需在 follow-up issue 提案並
  納入白名單）時，須新增一則 `<incidents_dir>/<slug>.md` fragment。
- **Fail/Warn 語意**：帶標籤但未新增 fragment → FAIL；未宣告 `incidents_dir` → NA。

### 3.3 小結：新增面

Stage 3 落地時，新增面 = **3 條新 rule_id（ISO-01/02/03/04；ISO-02 需 `RuleContext` 擴充，
排在最後）+ 1 個既有 R-25 extractor kind（`config_list`，涵蓋原 ISO-05 想法）**。全部 opt-in，
未宣告 `iso42001` 的既有 repo 零行為變更。

## 4. 明確的「不做」邊界 —— 六條設計原則逐條落實

| 原則 | 落實到的設計決策 |
|---|---|
| **no self-certification** | ISO-02 明確要求「非作者」核准，且是本設計中唯一要求人工介入才能 PASS 的規則；其餘所有 R-NN/ISO-NN 規則的「能證明」欄位都刻意排除「這個變更是安全的／合規的」這類判斷——它們只證明「宣稱的治理動作有沒有留痕」，判斷永遠留給人 |
| **one authority per fact** | `iso42001.systems[].id` 是系統盤點的唯一權威來源，ISO-01 的關聯規則要求 fragment 反過來引用該 `id`（不允許 fragment 自己另編一套系統命名）；比照 R-14/R-20/R-23 既有「單一宣告值、其餘處全部比對」的模式，不重複發明 |
| **artifact before transition** | 每條新規則都是「變更命中條件 → 必須先有對應產物才能視為完成」的 gate 形狀（ISO-01 fragment、ISO-03 provenance 文件、ISO-04 incident fragment），與 R-09/R-19 現有「先有證據才能 claim done」的形狀一致，不引入「先做再補」的例外 |
| **bounded governance** | 整個 profile 掛在單一 opt-in 頂層 key `iso42001` 之下；§1 明確聲明未宣告時所有 ISO-NN 規則 NA，對現有下游 repo 是 no-op；Stage 2 schema 落地本身也不啟用任何新 FAIL 語意 |
| **physical reality wins** | §2 對映表的每一列都寫了「不能證明」；ISO-02 在 review 資料不可得時降級 WARN 而非用「文件宣稱過」頂替，正是「機械只認得到的到才算數，認不到就誠實說不知道」的具體做法 |
| **copyright-safe mapping** | 見 §0：只到 clause/Annex A 分類層級、不轉錄原文、明講最終需以正式文本核對；§2 表格的「對映分類方向」欄位一律標注「方向」二字，避免讀者誤認為逐條認證對照表 |

## 5. 著作權安全

- 本文件與規劃中的所有規則程式碼、config schema、文件字串，**只使用 ISO/IEC 42001:2023
  的 clause 編號（4–10）與 Annex A 分類編號（A.2–A.10）+ 我方自撰的分類主題摘要**（如
  「Annex A.7 方向：AI 系統所用資料的文件化」），該摘要是本專案對分類**用途**的理解與
  重新表述，不是標準原文的翻譯或節錄。
- 未來 Stage 2/3 的程式碼註解、rule docstring、schema 說明文字，比照同樣原則：只寫
  「這條規則檢查什麼」的自撰工程描述，不引用或改寫標準條文用語。
- 任何需要逐條 sub-control 級精確映射的場景（例如未來要準備稽核佐證清單），**須由取得
  正式授權文本的人員核對**，不可直接沿用本文件的分類層級映射當作逐條對照表。
- 本文件與規劃的規則本身不對外宣稱「符合 ISO/IEC 42001」或作為任何形式的認證聲明；
  它是内部工程證據收集機制的設計文件。

## 6. 階段規劃

| 階段 | 內容 | 驗收條件 |
|---|---|---|
| **Stage 1（本次）** | 設計文件 + MOC 同步 + changelog fragment；不改 `policy_check/**` | 本文件通過 review；`docs/MOC.md` 連結本文件（R-24）；`pytest -q` / `policy_check --repo .` 皆無變化 |
| **Stage 2 — schema 落地** | R-08 新增 `iso42001` 區塊驗證（`systems`/`third_party_components`/`data_provenance_doc`/`incidents_dir` 形狀；`systems[].id` 唯一性）；純 schema，不新增任何會 FAIL 的行為規則 | R-08 測試涵蓋 `iso42001` 各子欄位的型別/必要 key/id 唯一性正例反例；既有 repo（未宣告 `iso42001`）之 `policy_check --repo .` 結果不變（回歸測試） |
| **Stage 3 — 規則實作** | 依 §3 逐條落地：先 ISO-01（無需 `RuleContext` 擴充）→ ISO-03 → ISO-04 → R-25 `config_list` extractor → 最後 ISO-02（需 `RuleContext` + CI review-fetch 擴充，成本最高、排最後、可獨立成一個 follow-up） | 每條規則 TDD（先紅後綠），fixture 涵蓋 opt-in NA、PASS、FAIL、（ISO-02 另有）WARN；CLAUDE.md 白名單新增對應 exempt label 提案；README 規則總覽同步；本 repo 若自身宣告 `iso42001` 需自身 dogfood 通過 |

## 7. Follow-up issue 草稿

供人工開 issue 使用，供人工複製貼上：

---

**標題**：`實作 ISO/IEC 42001 opt-in profile — Stage 2 schema 落地`

**Body**：

```
承接 #60（ISO/IEC 42001 opt-in profile 設計，設計文件見
docs/superpowers/specs/2026-08-10-iso42001-profile-design.md）。

本 issue 對應設計文件 §6 Stage 2：只做 schema 落地，不新增任何會 FAIL 的行為規則。

## 範圍
- `policy_check/rules/r08_policy_config_schema.py` 新增 `iso42001` 區塊驗證：
  - `systems`：list[mapping]，每筆須含 `id`（str，repo 內唯一）、`owner`（str）、
    `intended_use`（str）、`risk_tier`（str）；`code_paths`/`data_paths` 選填 list[str]
  - `third_party_components`：list[mapping]，每筆須含 `name`（str）；`role`/`version_ref` 選填
  - `data_provenance_doc`：選填 str（repo-relative path）
  - `incidents_dir`：選填 str（repo-relative path）
- 全部欄位、整個 `iso42001` 區塊皆選填；未宣告時 R-08 對該 repo 的既有行為不變
- 新增/更新 `tests/test_rule_r08_policy_config_schema.py` 正例反例（含 id 重複反例）

## Out of scope（留給後續 issue）
- ISO-01～ISO-04 規則本體（見設計文件 §3.2）
- R-25 `config_list` extractor kind（見設計文件 §3.1）
- ISO-02 所需的 `RuleContext.pr_approvals` 擴充與 GitHub/GitLab review API 串接
  （設計文件已標注為成本最高項，建議獨立排期）

## 驗收
- `python3 -m pytest -q` 全綠
- `python3 -m policy_check --repo .` `fail: 0`
- README 規則總覽如涉及 R-08 schema 說明需同步（R-18）
```

---
