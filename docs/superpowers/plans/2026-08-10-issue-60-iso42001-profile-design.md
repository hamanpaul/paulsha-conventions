# Issue #60 — 設計 opt-in ISO/IEC 42001 engineering-evidence profile

- Issue: [#60](https://github.com/hamanpaul/paulsha-conventions/issues/60)（先 `gh issue view 60` 讀完整內容——issue 本身就是設計 brief：背景、可重用機制清單、六條設計原則、著作權邊界、原始標準來源全都在裡面）
- 工作分支：`feature/issue-60-iso42001-profile-design`（由派工系統建立）
- 狀態：派工中
- 性質：**docs-only 設計交付**——本分支不改任何 `policy_check/**` 程式碼；實作屬後續 scoped issue

## 交付物

1. **設計文件** `docs/superpowers/specs/2026-08-10-iso42001-profile-design.md`，必含章節：
   - **Opt-in 機制**：`.project-policy.yml` 如何宣告 profile（示意 schema）；預設完全不啟用、既有 repo 行為零變更（bounded governance）
   - **證據對映表**：可機械證明的 ISO/IEC 42001 工程證據 × 既有規則（issue 已點名 R-09/R-14/R-15/R-23/R-16/R-22/R-25/R-26/R-19/R-20），逐條寫「此規則能證明什麼、不能證明什麼」
   - **新規則規劃**：既有規則覆蓋不到的證據需求，以獨立命名空間（如 `ISO-NN`）規劃，不佔用 `R-NN`；每條列 evidence schema 草案與 fail/warn 語意
   - **明確的「不做」邊界**：issue 六條設計原則（no self-certification／one authority per fact／artifact before transition／bounded governance／physical reality wins／copyright-safe mapping）逐條落實到設計決策
   - **著作權安全**：只引用 clause/control ID 與自寫 implementation intent；文件內不得出現 ISO 條文原文；載明「最終 mapping 需以合法取得的正式文本核對」
   - **階段規劃**：設計（本次）→ schema 落地 → 規則實作，各階段驗收條件
   - **Follow-up issue 草稿**：文件末段附 scoped implementation issue 的草稿文字（標題 + body），供人工開 issue
2. **MOC 同步**：`docs/MOC.md` 的 Plans／相關段落連結本設計文件（R-24）

## Global constraints

- **不改任何程式碼**：只動 `docs/**` 與 `changelog.d/**`
- 新增 changelog fragment `changelog.d/60-iso42001-profile-design.md`（`type: docs`、`issue: 60`）
- 完成後 `python3 -m pytest -q` 全綠（不應有任何變化）、`python3 -m policy_check --repo .` `fail: 0`（R-24 對新文件的連結檢查通過）

## 驗收指令

```bash
python3 -m pytest -q
python3 -m policy_check --repo .
```

## 完成義務

全部變更 commit 到工作分支（conventional commit zh-tw，如 `docs(governance): ISO/IEC 42001 opt-in profile 設計（#60）`）。**不開 PR**。worktree 必須乾淨。
