# tests/test_doc_drift_refs.py
from policy_check.doc_drift import refs


def test_extract_symbol_and_path_tokens():
    text = "see `Foo.close` and `legacy_init`, file [x](../a.py)\n"
    got = list(refs.extract_refs("docs/g.md", text))
    kinds = {(kind, token) for (kind, token, _payload) in got}
    assert ("symbol", "Foo.close") in kinds
    assert ("symbol", "legacy_init") in kinds
    assert any(kind == "path" for (kind, _t, _p) in got)
