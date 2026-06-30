## 1. collate 工具（policy_check.changelog）

- [ ] 1.1 實作 `policy_check/changelog.py` 純邏輯：frontmatter 解析（`type` 必填、`scope`/`issue` 選填）、固定 type→KaC 段映射、未知 type raise、多 fragment 分組與段順序（Added→Changed→Deprecated→Removed→Fixed→Security）、產出 `## [X.Y.Z] - <date>` 段字串。
- [ ] 1.2 實作 I/O 邊緣與 `collate --version --date` CLI：讀 `changelog.d/*.md`、把 dated 段插入 `CHANGELOG.md`（`# Changelog` 之後、最新 dated 段之前）、刪除所有 fragment 檔（保留 `.gitkeep`）。
- [ ] 1.3 新增 `tests/test_changelog.py`：frontmatter 解析、type 映射、未知 type 失敗、分組排序、KaC 段產出、collate 後目錄清空。

## 2. 規則改寫（R-09 / R-04）

- [ ] 2.1 改 `R-09`：核心改為「`changed_files` 含 `changelog.d/*.md`」；保留 `code_paths` 觸發與 `skip-changelog` 豁免。更新／新增 `tests/test_rule_r09_code_changelog_sync.py`（有 fragment→PASS、無 fragment→FAIL、skip-changelog→SKIP、無 code 變動→PASS）。
- [ ] 2.2 改 `R-04`：移除 `## [Unreleased]` 必備要求，保留 `# Changelog` 與 dated 段格式驗證。更新 `tests/test_rule_r04_changelog_format.py`（無 [Unreleased] 仍 PASS、缺 `# Changelog`→FAIL）。

## 3. 本 repo dogfood 與文件

- [ ] 3.1 建 `changelog.d/`（`.gitkeep`）；移除本 repo `CHANGELOG.md` 的 `## [Unreleased]` 標頭（保留歷史 dated 段內容，不回頭重切舊版段）。
- [ ] 3.2 本案自身新增 fragment `changelog.d/24-changelog-fragments.md`（記錄本變更）。
- [ ] 3.3 更新 canonical `CLAUDE.md`：把 checklist 中「同步更新 CHANGELOG [Unreleased]」改為「新增 changelog.d/ fragment」；README 規則表（R-04/R-09 描述）+ 新增 fragment 模型與 `collate` 指令說明段。

## 4. 驗證

- [ ] 4.1 跑 `python3 -m pytest -q` 與 `python3 -m policy_check --repo .` 全綠（R-09 認本案的 fragment、R-04 無 [Unreleased] 仍過），確認 feature batch ready for review and archive。
