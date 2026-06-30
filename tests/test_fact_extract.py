from __future__ import annotations

import pytest

from policy_check.rules import _fact_extract as fe


# ---- fact identity / extraction ----

def test_modules_distinct_by_full_path_not_basename():
    files = ["pkg/a/auth.py", "pkg/b/auth.py", "pkg/a/__init__.py"]
    src = {"kind": "modules", "include": ["pkg/**/*.py"], "exclude": ["**/__init__.py"]}
    facts = fe.extract_file_facts(src, files, lambda rel: "")
    assert facts == {"pkg/a/auth.py", "pkg/b/auth.py"}


def test_rpc_methods_use_capture_group():
    files = ["svc.py"]
    texts = {"svc.py": 'if method == "session.renumber":\n    ...\nif method == "session.close":\n    ...\n'}
    src = {"kind": "rpc_methods", "include": ["svc.py"], "pattern": r'method\s*==\s*"([^"]+)"'}
    facts = fe.extract_file_facts(src, files, lambda rel: texts.get(rel))
    assert facts == {"session.renumber", "session.close"}


def test_env_vars_prefix_tokens():
    files = ["conf.py"]
    texts = {"conf.py": "os.environ['SERIALWRAP_SOCKET_PATH']\nSERIALWRAP_TIMEOUT = 5\nOTHER_VAR = 1\n"}
    src = {"kind": "env_vars", "include": ["conf.py"], "prefix": "SERIALWRAP_"}
    facts = fe.extract_file_facts(src, files, lambda rel: texts.get(rel))
    assert facts == {"SERIALWRAP_SOCKET_PATH", "SERIALWRAP_TIMEOUT"}


def test_cli_tree_one_fact_per_stdout_line():
    src = {"kind": "cli_tree", "command": "python3 -c \"print('serialwrap session renumber'); print('serialwrap session close')\""}
    facts = fe.extract_cli_facts(src, ".")
    assert facts == {"serialwrap session renumber", "serialwrap session close"}


def test_cli_tree_nonzero_exit_raises():
    src = {"kind": "cli_tree", "command": "python3 -c \"import sys; sys.exit(3)\""}
    with pytest.raises(fe.ExtractorError):
        fe.extract_cli_facts(src, ".")


# ---- source config validation ----

def test_validate_source_rejects_unknown_kind():
    assert fe.validate_source({"kind": "wat"}) is not None


def test_validate_source_requires_include_for_modules():
    assert fe.validate_source({"kind": "modules"}) is not None
    assert fe.validate_source({"kind": "modules", "include": ["a/**"]}) is None


def test_validate_source_rpc_pattern_must_have_one_group():
    assert fe.validate_source({"kind": "rpc_methods", "include": ["s.py"], "pattern": "no_group"}) is not None
    assert fe.validate_source({"kind": "rpc_methods", "include": ["s.py"], "pattern": "(a)(b)"}) is not None
    assert fe.validate_source({"kind": "rpc_methods", "include": ["s.py"], "pattern": '"([^"]+)"'}) is None


def test_validate_source_env_requires_prefix():
    assert fe.validate_source({"kind": "env_vars", "include": ["s.py"]}) is not None
    assert fe.validate_source({"kind": "env_vars", "include": ["s.py"], "prefix": "X_"}) is None


def test_validate_source_cli_requires_command():
    assert fe.validate_source({"kind": "cli_tree"}) is not None
    assert fe.validate_source({"kind": "cli_tree", "command": "echo hi"}) is None


# ---- mention matching (exact token/phrase, case-sensitive, no substring) ----

def test_is_mentioned_exact_token():
    assert fe.is_mentioned("session.renumber", "see `session.renumber` for details")


def test_is_mentioned_rejects_substring():
    # session.close must not be satisfied by session.closed
    assert not fe.is_mentioned("session.close", "use session.closed flag")


def test_is_mentioned_path_not_confused_by_longer_path():
    assert fe.is_mentioned("pkg/a/auth.py", "module `pkg/a/auth.py`")
    assert not fe.is_mentioned("pkg/a/auth.py", "module `pkg/a/auth.pyc`")


def test_is_mentioned_phrase_with_spaces():
    assert fe.is_mentioned("serialwrap session renumber", "run `serialwrap session renumber` now")
    assert not fe.is_mentioned("serialwrap session renumber", "run serialwrap session renumbered now")


def test_is_mentioned_case_sensitive():
    assert not fe.is_mentioned("SERIALWRAP_TIMEOUT", "serialwrap_timeout is set")


# ---- review hardening (M1 / M2) ----

def test_rpc_methods_ignores_unmatched_or_empty_capture():
    # An optional capture group that does not participate must not yield a None/'' fact.
    files = ["s.py"]
    texts = {"s.py": "bar\nxbar\n"}
    src = {"kind": "rpc_methods", "include": ["s.py"], "pattern": r"(x)?bar"}
    facts = fe.extract_file_facts(src, files, lambda rel: texts.get(rel))
    assert facts == {"x"}


def test_env_vars_prefix_requires_left_boundary():
    # Prefix must start a token; it must not be pulled out of a longer identifier.
    files = ["c.py"]
    texts = {"c.py": "MAX_SWAP_SIZE = 1\nSWAP_TOTAL = 2\n"}
    src = {"kind": "env_vars", "include": ["c.py"], "prefix": "SWAP_"}
    facts = fe.extract_file_facts(src, files, lambda rel: texts.get(rel))
    assert facts == {"SWAP_TOTAL"}
