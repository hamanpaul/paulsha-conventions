## Why

`serialwrap`、`testpilot`、`paulshaclaw` 等 repo 歷經架構調整後，文件常殘留舊架構/過時引用，現有規則抓不到（R-18 只看「PR 有沒有碰 docs」、不看內容）。需要一條可重現的確定性規則，在 CI 擋下「文件引用了已不存在的 code 產物」這類結構性陳舊（issue #11）。

## What Changes

- **新增引擎規則 R-22（doc-reference）**：掃 `README.md` + `docs/**` 的**結構化引用**（檔案路徑、markdown 內部連結、反引號 token），偵測懸空引用。
  - **Prong P**（路徑/連結，doc-driven 快照）：引用目標在 head 不存在即懸空。
  - **Prong S**（symbol，diff-driven）：本次 `base..head` 刪/改名的 Python `def`/`class`，若 docs 仍引用則命中；不做全域 symbol 稽核。
  - **diff-aware 分級**：本次新破壞 → FAIL；陳年懸空 → WARN；無 diff context（本地）→ Prong P 降 WARN、Prong S 關閉。
- **`.paul-project.yml` 新增 `doc_reference.allow`**（doc-path glob 逃生閥）；**R-08 schema** 驗證其為 `list[str]`。
- **豁免 label** `policy-exempt:doc-reference`。
- **Tier 1 / Tier 3（四份 agent 檔同步、advisory）**：checklist 加 R-22 條目與白名單；新增「PR review 時留意語意陳舊」導引（Copilot 等做 review 的 agent 共用）。
- **README**：規則表 + 豁免清單 + 「Doc-alignment governance（三層）」段。
- 掃描排除 `openspec/**`、`docs/superpowers/**` 與規則自身 fixtures（self-exempt）。

## Capabilities

### New Capabilities
- `doc-reference`: R-22 確定性懸空引用偵測（結構化引用、diff-aware 分級、本地優雅降級）及其 `.paul-project.yml` 設定與 R-08 schema 驗證。

### Modified Capabilities
<!-- 無：R-08 對 doc_reference 的 schema 驗證屬 doc-reference capability 自身契約，不改既有 capability 的需求。 -->

## Impact

- **引擎**：`policy_check/rules/r22_doc_reference.py`（新）、`policy_check/rules/r08_policy_config_schema.py`（擴充）。
- **測試**：`tests/test_rule_r22_doc_reference.py`、`tests/fixtures/doc-reference/**`、R-08 測試擴充。
- **設定**：`.paul-project.yml`（`doc_reference.allow`，自身 dogfood）。
- **agent 慣例檔（四份同步）**：`CLAUDE.md` / `AGENTS.md` / `GEMINI.md` / `.github/copilot-instructions.md`。
- **文件 / 版本**：`README.md`、`CHANGELOG.md`；發版時 `VERSION` / `pyproject.toml` / `.paul-project.yml` / 四份 agent 檔 `policy_version` → **1.1.0**（MINOR），補 `RELEASES.md` 一列。
- **下游**：陳年 rot 僅 WARN、不擋，導入無痛；按步調 pin 新 engine SHA + 設 `policy_version: 1.1.0`。
