# tests/test_doc_drift_exempt.py
from policy_check.doc_drift import exempt


def test_inline_marker_suppresses_line():
    text = "call `gone` <!-- doc-drift-ignore -->\n"
    assert exempt.line_is_ignored(text.splitlines()[0]) is True


def test_allowlist_symbol_match():
    allow = exempt.parse_allowlist(["symbol:gone", "docs/legacy/*"])
    assert exempt.is_allowed("docs/a.md", "gone", allow) is True
    assert exempt.is_allowed("docs/legacy/x.md", "anything", allow) is True
    assert exempt.is_allowed("docs/a.md", "kept", allow) is False
