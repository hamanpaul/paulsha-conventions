# tests/test_doc_drift_langs.py
from policy_check.doc_drift import langs


def test_python_public_kinds():
    assert langs.public_kinds("Python") == {"function", "class", "member"}


def test_unknown_language_has_no_kinds():
    assert langs.public_kinds("Haskell") == set()


def test_python_is_supported():
    assert "Python" in langs.supported_languages()
