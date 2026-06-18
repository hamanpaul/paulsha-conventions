## 1. TDD RED（測試先行）

- [ ] 1.1 建立 fixtures `tests/fixtures/doc-reference/**`：clean、路徑本次刪除、陳年懸空、symbol 本次移除、symbol 仍存在、豁免 label、allow-glob 命中、無 base、`openspec/**` 與 `docs/superpowers/**` 排除
- [ ] 1.2 寫 `tests/test_rule_r22_doc_reference.py`，逐一對應 spec scenario，用真實 temp git repo（base/head commit）驅動
- [ ] 1.3 擴充 R-08 測試：`doc_reference.allow` 非 `list[str]` → FAIL；合法陣列 → 通過
- [ ] 1.4 跑測試確認 RED，且失敗原因正確（rule/欄位尚未存在），擷取 RED 輸出為證

## 2. R-22 引擎

- [ ] 2.1 `policy_check/rules/r22_doc_reference.py`：掃描範圍（`README.md`+`docs/**`）與排除（`openspec/**`、`docs/superpowers/**`、自身 fixtures、`doc_reference.allow`）
- [ ] 2.2 Prong P：抽 markdown 內部連結與 path-shaped token，對 head git-tracked 檔案解析存在性
- [ ] 2.3 diff seam：給定 repo_root + base_ref 回傳（本次移除 symbols、base tracked 檔案集合）；無 base 時降級
- [ ] 2.4 Prong S：從 `base..head` 找本次刪/改名的 Python `def`/`class`，比對 docs 反引號引用
- [ ] 2.5 嚴重度分級：新破壞 FAIL、陳年 WARN、無 diff → Prong P 降 WARN + Prong S 關閉
- [ ] 2.6 豁免 label `policy-exempt:doc-reference` → SKIP；`@register` 註冊規則
- [ ] 2.7 跑 R-22 測試轉 GREEN

## 3. R-08 schema 擴充

- [ ] 3.1 `r08_policy_config_schema.py`：`doc_reference.allow` 存在時驗為 `list[str]`，型別不符 FAIL
- [ ] 3.2 跑 R-08 測試轉 GREEN

## 4. 設定 dogfood

- [ ] 4.1 `.paul-project.yml` 新增 `doc_reference.allow`（必要的自身合法引用）

## 5. Tier 1 / Tier 3（四份 agent 檔同步）

- [ ] 5.1 四份檔「改 code 時」「claim done 前」加 R-22 條目；白名單加 `policy-exempt:doc-reference`
- [ ] 5.2 四份檔新增「Doc-alignment review（PR review 時）」語意陳舊導引段
- [ ] 5.3 四份檔「改版號時／claim done 前」新增 convention：PR 若 defer 版本 bump，merge 當下必須立即補做（`VERSION`/`policy_version`/四份檔/`managed-by`/tag/`RELEASES.md`）
- [ ] 5.4 確認四份內容一致（R-13/R-14 綠）

## 6. README

- [ ] 6.1 規則總覽表加 R-22 列、豁免清單加一筆、新增「Doc-alignment governance（三層）」段（含建議設 Copilot 為 reviewer）

## 7. CHANGELOG 與驗證

- [ ] 7.1 `CHANGELOG.md [Unreleased]` 加 R-22 + 三層治理 entry（版本號待定，見下方註）
- [ ] 7.2 全套 `python3 -m pytest -q` 綠
- [ ] 7.3 `python3 -m policy_check --repo .` fail:0 / warn:0（self-dogfood）

> 註：版本級別 **1.0.5（PATCH）**；本實作 PR 不 bump，R-22 先進 `[Unreleased]`。`policy_version`
> bump、`v1.0.5` tag、`RELEASES.md` 回填屬 **merge 當下立即執行** 的 release 步驟（見 design
> §Migration），並由 task 5.3 的新 convention 固化此要求。
