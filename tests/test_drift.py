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


# --- safe_classify：malformed 不炸，回 'invalid' ---
def test_safe_classify_invalid_does_not_raise():
    assert drift.safe_classify("1.0", "1.0.7") == "invalid"
    assert drift.safe_classify("garbage", "1.0.7") == "invalid"


def test_safe_classify_passthrough():
    assert drift.safe_classify("1.0.5", "1.0.7") == "behind"
    assert drift.safe_classify(None, "1.0.7") == "unmanaged"


# --- format_report ---
def test_format_report_contains_rows_and_canonical():
    out = drift.format_report(
        [("alpha", "1.0.5", "behind"), ("beta", None, "unmanaged")], "1.0.7"
    )
    assert "canonical: 1.0.7" in out
    assert "behind" in out
    assert "unmanaged" in out


# --- local_policy_version：兩種設定檔名都認（含 legacy .project-policy.yml） ---
def test_local_policy_version_reads_paul_project(tmp_path):
    (tmp_path / ".paul-project.yml").write_text(
        "policy_profile: flat\npolicy_version: 1.0.5\n", encoding="utf-8"
    )
    assert drift.local_policy_version(str(tmp_path)) == "1.0.5"


def test_local_policy_version_reads_legacy_project_policy(tmp_path):
    # 用舊檔名的 repo 不可被誤判為 unmanaged（否則 freshness gate 靜默放行）
    (tmp_path / ".project-policy.yml").write_text(
        "policy_profile: flat\npolicy_version: 1.0.5\n", encoding="utf-8"
    )
    assert drift.local_policy_version(str(tmp_path)) == "1.0.5"


def test_local_policy_version_absent_is_none(tmp_path):
    assert drift.local_policy_version(str(tmp_path)) is None


# --- check 子命令 exit code 契約（用 --against 離線，不碰 gh） ---
def test_check_behind_exits_nonzero(tmp_path):
    (tmp_path / ".paul-project.yml").write_text(
        "policy_profile: flat\npolicy_version: 1.0.5\n", encoding="utf-8"
    )
    assert drift.main(["check", "--repo", str(tmp_path), "--against", "1.0.7"]) == 1


def test_check_current_exits_zero(tmp_path):
    (tmp_path / ".paul-project.yml").write_text(
        "policy_profile: flat\npolicy_version: 1.0.7\n", encoding="utf-8"
    )
    assert drift.main(["check", "--repo", str(tmp_path), "--against", "1.0.7"]) == 0


def test_check_unmanaged_exits_zero(tmp_path):
    # 無設定檔 → unmanaged → 不擋
    assert drift.main(["check", "--repo", str(tmp_path), "--against", "1.0.7"]) == 0


def test_check_invalid_local_version_fails_closed(tmp_path):
    (tmp_path / ".paul-project.yml").write_text(
        "policy_profile: flat\npolicy_version: 1.0\n", encoding="utf-8"
    )
    assert drift.main(["check", "--repo", str(tmp_path), "--against", "1.0.7"]) == 1


# --- report 子命令：單一壞 repo 不致整份報表崩潰，仍 exit 0 ---
def test_report_survives_malformed_repo(monkeypatch, capsys):
    monkeypatch.setattr(drift, "canonical_version_live", lambda *a, **k: "1.0.7")
    monkeypatch.setattr(drift, "list_managed_repos", lambda *a, **k: ["good", "bad", "old"])
    versions = {"good": "1.0.7", "bad": "1.0", "old": "1.0.5"}
    monkeypatch.setattr(drift, "fetch_policy_version", lambda org, repo: versions[repo])

    rc = drift.main(["report", "--org", "hamanpaul"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "good" in out and "current" in out
    assert "bad" in out and "invalid" in out  # 壞 repo 標 invalid，不炸
    assert "old" in out and "behind" in out
