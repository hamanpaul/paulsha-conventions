# Bad demo

呼叫 `do_shutdown` 來關閉服務。但 `pkg/api.py` 已在本次變更刪掉 `do_shutdown`，
故 doc-drift 會回報 FAIL（exit 1）——這正是要被攔下的懸空 symbol 引用。
