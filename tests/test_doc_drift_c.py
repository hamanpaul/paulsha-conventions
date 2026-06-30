# tests/test_doc_drift_c.py
from policy_check.doc_drift import symbols, langs


def test_c_function_extracted():
    assert "C" in langs.supported_languages()
    lines = ['{"_type":"tag","name":"wifi_init","language":"C","kind":"function"}']
    assert ("C", "function", "", "wifi_init") in symbols.parse_ctags_json(lines)


def test_cpp_method_scoped():
    assert "C++" in langs.supported_languages()
    lines = ['{"_type":"tag","name":"start","language":"C++","kind":"function","scope":"Engine","scopeKind":"class"}']
    assert ("C++", "function", "Engine", "start") in symbols.parse_ctags_json(lines)
