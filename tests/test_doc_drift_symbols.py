# tests/test_doc_drift_symbols.py
from policy_check.doc_drift import symbols

# 取自 `ctags --output-format=json` 對 Foo.close / Bar.close / top_level 的實際輸出
_JSON_LINES = [
    '{"_type":"tag","name":"Foo","language":"Python","kind":"class"}',
    '{"_type":"tag","name":"Bar","language":"Python","kind":"class"}',
    '{"_type":"tag","name":"close","language":"Python","kind":"member","scope":"Foo","scopeKind":"class"}',
    '{"_type":"tag","name":"close","language":"Python","kind":"member","scope":"Bar","scopeKind":"class"}',
    '{"_type":"tag","name":"top_level","language":"Python","kind":"function"}',
    '{"_type":"tag","name":"x","language":"Python","kind":"variable"}',  # 非 public kind，應濾掉
    'not-json-noise',  # robust：跳過壞行
]


def test_parse_keeps_only_public_kinds_with_scope():
    got = symbols.parse_ctags_json(_JSON_LINES)
    assert ("Python", "class", "", "Foo") in got
    assert ("Python", "member", "Foo", "close") in got
    assert ("Python", "member", "Bar", "close") in got
    assert ("Python", "function", "", "top_level") in got
    # variable 不在白名單
    assert not any(name == "x" for (_l, _k, _s, name) in got)


def test_foo_and_bar_close_are_distinct_identities():
    got = symbols.parse_ctags_json(_JSON_LINES)
    closes = {ident for ident in got if ident[3] == "close"}
    assert closes == {
        ("Python", "member", "Foo", "close"),
        ("Python", "member", "Bar", "close"),
    }
