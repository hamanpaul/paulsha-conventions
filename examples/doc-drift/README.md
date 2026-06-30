# doc-drift demo fixtures

兩個對照組，示範 doc↔code symbol drift 的判定：

- `good/` — `docs/guide.md` 引用 `do_shutdown`，且 `pkg/api.py` 仍定義它 → 乾淨（exit 0）。
- `bad/` — `docs/guide.md` 仍引用 `do_shutdown`，但 `pkg/api.py` 已在本次變更移除它 → FAIL（exit 1）。

> 這些是「靜態示範用」資料；CI 的 self-test 以 `tests/test_doc_drift_demo.py`
> 在臨時 git repo 中重建 base→head 兩個 commit 來實際驗證 green/red 與 exit code，
> 並故意使用 `fetch-depth: 1` 的 shallow checkout 來驗證 Action 自取 base 物件不會前置失敗。

## 跑法（概念）

```bash
python3 -m policy_check.doc_drift \
  --mode doc-drift --repo <repo> --base <base-sha> --head HEAD
```

removed symbol 被 doc 引用 → 印出 `FAIL <doc> -> \`<symbol>\` (symbol removed this change)` 並 exit 1。
