# tests/test_doc_drift_bash.py
from policy_check.doc_drift import symbols, langs


def test_bash_function_extracted():
    assert "Sh" in langs.supported_languages()
    lines = ['{"_type":"tag","name":"do_build","language":"Sh","kind":"function"}']
    assert ("Sh", "function", "", "do_build") in symbols.parse_ctags_json(lines)
