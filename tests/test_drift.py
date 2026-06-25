from __future__ import annotations

import pytest

from policy_check import drift


# --- parse_version：-fix.N 完整排序 ---
def test_parse_version_absent_fix_is_zero():
    assert drift.parse_version("1.0.7") == (1, 0, 7, 0)


def test_parse_version_with_fix():
    assert drift.parse_version("1.0.7-fix.2") == (1, 0, 7, 2)


def test_no_suffix_sorts_below_fix1():
    assert drift.parse_version("1.0.7") < drift.parse_version("1.0.7-fix.1")


def test_fix_numeric_ordering():
    assert drift.parse_version("1.0.7-fix.2") > drift.parse_version("1.0.7-fix.1")


def test_parse_version_invalid_raises():
    with pytest.raises(ValueError):
        drift.parse_version("not-a-version")


# --- classify ---
def test_classify_behind():
    assert drift.classify("1.0.5", "1.0.7") == "behind"


def test_classify_current():
    assert drift.classify("1.0.7", "1.0.7") == "current"


def test_classify_ahead():
    assert drift.classify("1.0.8", "1.0.7") == "ahead"


def test_classify_hotfix_behind():
    # 落後但自洽的 hotfix 級漂移必須被抓
    assert drift.classify("1.0.7", "1.0.7-fix.2") == "behind"


def test_classify_unmanaged():
    assert drift.classify(None, "1.0.7") == "unmanaged"


# --- highest_version：從 tag 清單挑最高 vX.Y.Z[-fix.N] ---
def test_highest_version_picks_max():
    tags = ["v1.0.6", "v1.0.7", "v1.0.5", "v1.0.2"]
    assert drift.highest_version(tags) == "1.0.7"


def test_highest_version_respects_fix_suffix():
    assert drift.highest_version(["v1.0.7", "v1.0.7-fix.1"]) == "1.0.7-fix.1"


def test_highest_version_ignores_non_version_tags():
    assert drift.highest_version(["nightly", "v1.0.7", "latest"]) == "1.0.7"


def test_highest_version_no_tags_raises():
    with pytest.raises(ValueError):
        drift.highest_version(["nightly", "latest"])


# --- parse_policy_version ---
def test_parse_policy_version_extracts():
    text = "policy_profile: flat\npolicy_version: 1.0.7\n"
    assert drift.parse_policy_version(text) == "1.0.7"


def test_parse_policy_version_absent():
    assert drift.parse_policy_version("policy_profile: flat\n") is None


# --- format_report ---
def test_format_report_contains_rows_and_canonical():
    out = drift.format_report(
        [("alpha", "1.0.5", "behind"), ("beta", None, "unmanaged")], "1.0.7"
    )
    assert "canonical: 1.0.7" in out
    assert "behind" in out
    assert "unmanaged" in out
