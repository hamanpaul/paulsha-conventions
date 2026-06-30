# doc-drift Action

語言無關、零設定的 doc↔code 漂移檢查 composite action。把 paulsha-conventions
的 R-22（doc 對 code 產物的懸空引用）與 R-24（MOC 對齊）核心抽成可被**任意 repo**
`uses:` 的獨立 Action，無需目標 repo 採用 `.paul-project.yml`／profile/version 機制。

## 定位

- **確定性 gate**：只看「結構性 rot」——doc 引用的 path／內部連結／反引號 symbol 是否真實存在。
  不判斷語意（描述是否過時交給 reviewer/Copilot），不檢外部 URL 活性（交給 lychee）。
- **本次新破壞 FAIL、陳年懸空 WARN**：以 PR base→head 差集判定。FAIL 以非零 exit code 擋 merge，WARN 為 advisory（不擋）。
- **語言無關 scoped identity**：symbol 抽取用 universal-ctags JSON 輸出，比對 `(language, kind, scope, name)`
  四元組差集求 removed。限定式 token（如 `Foo.bar`）精準命中；裸名（`bar`）在多 scope 同名時只 WARN（不誤擋）。

## 輸入

| input | 預設 | 說明 |
|-------|------|------|
| `mode` | `doc-drift` | `doc-drift`（refs + paths + symbols）或 `moc`（refs + paths + coverage/orphan）。 |
| `base-sha` | （取自 event） | PR base 的精確 SHA。未提供時用 `github.event.pull_request.base.sha`。 |

## 輸出與 exit code

- 列出可定位的清單：`<檔案> -> <引用>`，FAIL 行前綴 `FAIL`、WARN 行前綴 `WARN`。
- 存在 FAIL 級懸空時以**非零 exit code** 結束（擋 merge）；僅陳年 WARN 時以 **0** 結束。
- 無法決定 base SHA（非 PR 事件或未提供 `base-sha`）時 fail-fast，exit 2 並輸出可行動訊息。

## base 供給契約

Action **自理** base/head 物件供給，不依賴 caller 的 `actions/checkout` 深度：從 GitHub event 取得
base/head 精確 SHA，委由核心 `provision.ensure_object` 確認物件存在（`git cat-file` 驗證，缺則
`git fetch` fallback）。因此在預設 `fetch-depth: 1` 的 shallow checkout 下也能完成分析、不前置失敗。

## `uses:` 片段

```yaml
name: doc-drift
on: [pull_request]

permissions:
  contents: read

jobs:
  doc-drift:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4        # 預設 fetch-depth: 1 即可
      - uses: hamanpaul/paulsha-conventions/.github/actions/doc-drift@<sha>
        # with:
        #   mode: doc-drift              # 或 moc
        #   base-sha: ${{ github.event.pull_request.base.sha }}
```

Action 步驟會自行安裝 universal-ctags（`apt-get install -y universal-ctags`）。

## 與 lychee 的互補

本 Action **不**檢查外部 URL 活性／HTTP 狀態／anchor——那屬 [lychee](https://github.com/lycheeverse/lychee-action)
的範圍。兩者互補：**lychee 管外部連結存活，doc-drift 管 in-repo 的 code 產物引用不懸空**。
建議在同一 PR workflow 並列兩個 job。

## 多語言支援

symbol 抽取的 public kind 白名單（`policy_check/doc_drift/langs.py`）：

| ctags language | 計為 public symbol 的 kind |
|----------------|----------------------------|
| Python | function、class、member |
| Sh（bash） | function |
| C | function、struct、typedef、macro、enum |
| C++ | function、class、struct、member、typedef、macro、enum |

新增語言只動這張表，差集／比對演算法不變。

## 已知侷限

- **裸名歧義只 WARN**：doc 用裸名（無 scope 限定）引用一個在多個 scope 同名的 symbol 時，
  為避免誤擋只回 WARN，不 FAIL。要精準命中請在 doc 用限定式（`Class.method`）。
- 只覆蓋上表語言；未登錄語言的 symbol 不納入差集（不誤報，但也不偵測）。
- 不做語意陳舊判斷（引用仍在但描述過時）；該層交由 PR reviewer/Copilot（advisory）。

## 誤報豁免

- **行內 marker**：在 doc 該行加 `<!-- doc-drift-ignore -->` 略過該行。
- **allowlist 檔**：repo 根的 `.doc-drift-allow` 列 `<doc路徑> <token>` 對，命中則跳過。

## demo 與 self-test

`examples/doc-drift/` 提供 green（引用存在）／known-bad（引用本次被移除）兩組對照；
CI self-test（`tests/test_doc_drift_demo.py`，`.github/workflows/self-test.yml`）在臨時 git repo
重建 base→head 兩 commit 實際斷言 green=exit0／red=exit1，並故意用 `fetch-depth: 1` shallow checkout
驗證 Action 自取 base 物件不前置失敗。
