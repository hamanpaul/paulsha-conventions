# tests/test_doc_drift_drift.py
from policy_check.doc_drift import drift

BASE = {
    ("Python", "member", "Foo", "close"),
    ("Python", "member", "Bar", "close"),
    ("Python", "function", "", "legacy_init"),
}
# HEAD：移除 Foo.close（保留 Bar.close）、移除 legacy_init
HEAD = {
    ("Python", "member", "Bar", "close"),
}


def test_removed_identities():
    removed = drift.removed_identities(BASE, HEAD)
    assert ("Python", "member", "Foo", "close") in removed
    assert ("Python", "function", "", "legacy_init") in removed
    assert ("Python", "member", "Bar", "close") not in removed


def test_qualified_ref_to_removed_is_fail():
    removed = drift.removed_identities(BASE, HEAD)
    assert drift.classify_symbol_token("Foo.close", removed, HEAD) == "FAIL"


def test_bare_ref_partial_removal_is_warn():
    removed = drift.removed_identities(BASE, HEAD)
    # close 仍存在於 Bar → 歧義
    assert drift.classify_symbol_token("close", removed, HEAD) == "WARN"


def test_bare_ref_fully_vanished_is_fail():
    removed = drift.removed_identities(BASE, HEAD)
    assert drift.classify_symbol_token("legacy_init", removed, HEAD) == "FAIL"


def test_unrelated_token_is_none():
    removed = drift.removed_identities(BASE, HEAD)
    assert drift.classify_symbol_token("something_else", removed, HEAD) is None
    # Bar.close 未被移除
    assert drift.classify_symbol_token("Bar.close", removed, HEAD) is None
