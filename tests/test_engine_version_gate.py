from __future__ import annotations

from pathlib import Path

import pytest

from policy_check import cli
from policy_check import config as cfg
from policy_check import engine_gate
from policy_check import report
from policy_check.rules.base import RuleResult, Status

REPO = Path(__file__).resolve().parents[1]


def _write_repo(tmp_path: Path, policy_version: str) -> None:
    (tmp_path / ".project-policy.yml").write_text(
        f"policy_profile: flat\npolicy_version: {policy_version}\n",
        encoding="utf-8",
    )


# ---- resolve_engine_version() ----


def test_resolve_engine_version_prefers_installed_metadata(monkeypatch):
    monkeypatch.setattr(engine_gate, "_installed_version", lambda: "9.9.9")
    version = engine_gate.resolve_engine_version()
    assert version == engine_gate.EngineVersion("9.9.9", "installed package")


def test_resolve_engine_version_falls_back_to_source_checkout(monkeypatch):
    # 不得誤殺情境 1：conventions repo 自身 source checkout 開發，引擎版本來源
    # = repo VERSION，與 policy_version 天然一致。
    monkeypatch.setattr(engine_gate, "_installed_version", lambda: None)
    version = engine_gate.resolve_engine_version()
    repo_version = (REPO / "VERSION").read_text(encoding="utf-8").strip()
    assert version == engine_gate.EngineVersion(repo_version, "source checkout")


def test_resolve_engine_version_fails_closed_when_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(engine_gate, "_installed_version", lambda: None)
    monkeypatch.setattr(engine_gate, "_ENGINE_ROOT", tmp_path)
    with pytest.raises(engine_gate.EngineVersionError, match="cannot determine"):
        engine_gate.resolve_engine_version()


def test_engine_version_error_mirrors_config_error_family():
    # 比照 "Missing .project-policy.yml" 的處理路徑：同一個例外家族，
    # cli.main() 既有的 `except cfg.ConfigError` 才能原樣接住。
    assert issubclass(engine_gate.EngineVersionError, cfg.ConfigError)


# ---- check() ----


def test_check_passes_when_versions_match(monkeypatch):
    monkeypatch.setattr(engine_gate, "_installed_version", lambda: "1.0.15")
    result = engine_gate.check("1.0.15")
    assert result.status == "pass"
    assert "1.0.15" in result.message


def test_check_normalizes_fix_suffix_before_comparing(monkeypatch):
    monkeypatch.setattr(engine_gate, "_installed_version", lambda: "1.0.15.post2")
    result = engine_gate.check("1.0.15-fix.2")
    assert result.status == "pass"


def test_check_fails_loud_on_mismatch_with_both_versions_in_message(monkeypatch):
    monkeypatch.setattr(engine_gate, "_installed_version", lambda: "1.0.10")
    with pytest.raises(engine_gate.EngineVersionError) as exc_info:
        engine_gate.check("1.0.15")
    message = str(exc_info.value)
    assert "1.0.10" in message
    assert "1.0.15" in message
    assert "pip install" in message


def test_check_normalizes_fix_suffix_in_reinstall_pip_spec(monkeypatch):
    # Copilot review (PR #67, comment 3749805792): 重裝指令必須用 PEP 440
    # 正規化後的版本字串組 pip spec，否則宣告 "1.0.15-fix.2" 時會產生
    # `policy-check==1.0.15-fix.2`，pip 裝不到（PEP 440 不接受 `-fix.N`）。
    monkeypatch.setattr(engine_gate, "_installed_version", lambda: "1.0.10")
    with pytest.raises(engine_gate.EngineVersionError) as exc_info:
        engine_gate.check("1.0.15-fix.2")
    message = str(exc_info.value)
    # 宣告文字維持原始 policy_version（供人閱讀比對）。
    assert "policy_version: 1.0.15-fix.2" in message
    # 但實際可執行的 pip spec 必須是正規化後的版本。
    assert "pip install --upgrade 'policy-check==1.0.15.post2'" in message
    assert "policy-check==1.0.15-fix.2" not in message


def test_check_downgrades_to_warn_under_release_label(monkeypatch):
    # 不得誤殺情境 2：release PR 上 VERSION 先行 bump 的窗口，比照 R-07。
    monkeypatch.setattr(engine_gate, "_installed_version", lambda: "1.0.10")
    result = engine_gate.check("1.0.15", pr_labels=["release:patch"])
    assert result.status == "warn"
    assert "1.0.10" in result.message
    assert "1.0.15" in result.message
    assert "release:patch" in result.message


def test_check_ignores_non_release_labels(monkeypatch):
    monkeypatch.setattr(engine_gate, "_installed_version", lambda: "1.0.10")
    with pytest.raises(engine_gate.EngineVersionError):
        engine_gate.check("1.0.15", pr_labels=["needs-review"])


def test_check_fails_closed_even_with_release_label_when_unavailable(monkeypatch, tmp_path):
    # 不得誤殺情境 3：無法取得引擎版本時 fail-closed，不得被 release label 靜默跳過。
    monkeypatch.setattr(engine_gate, "_installed_version", lambda: None)
    monkeypatch.setattr(engine_gate, "_ENGINE_ROOT", tmp_path)
    with pytest.raises(engine_gate.EngineVersionError):
        engine_gate.check("1.0.15", pr_labels=["release:patch"])


# ---- report header ----


def test_format_report_header_includes_value_and_source():
    line = engine_gate.format_report_header(
        engine_gate.EngineVersion("1.0.15", "installed package")
    )
    assert line == "Engine: policy-check 1.0.15 (installed package)"


def test_report_emit_prints_engine_version_header(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    results = [RuleResult("R-01", Status.PASS, "ok")]
    line = engine_gate.format_report_header(
        engine_gate.EngineVersion("1.0.15", "source checkout")
    )
    rc = report.emit(results, engine_version_line=line)
    out = capsys.readouterr().out
    assert out.startswith(
        "# Policy Check Report\n\nEngine: policy-check 1.0.15 (source checkout)\n"
    )
    assert rc == 0


def test_report_emit_omits_header_line_when_engine_version_not_given(capsys, monkeypatch):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    report.emit([RuleResult("R-01", Status.PASS, "ok")])
    out = capsys.readouterr().out
    assert "Engine:" not in out


# ---- cli wiring: startup gate fires before any rule runs ----


def test_cli_main_exits_2_on_engine_version_mismatch(monkeypatch, tmp_path, capsys):
    _write_repo(tmp_path, "1.0.15")
    monkeypatch.setattr(cli.prc, "load_pr_meta", lambda: {})
    monkeypatch.setattr(engine_gate, "_installed_version", lambda: "1.0.10")
    rc = cli.main(["--repo", str(tmp_path)])
    assert rc == 2
    err = capsys.readouterr().err
    assert "configuration error" in err
    assert "1.0.10" in err and "1.0.15" in err


def test_cli_main_warns_and_continues_under_release_label(monkeypatch, tmp_path, capsys):
    _write_repo(tmp_path, "1.0.15")
    monkeypatch.setattr(cli.prc, "load_pr_meta", lambda: {})
    monkeypatch.setattr(engine_gate, "_installed_version", lambda: "1.0.10")
    monkeypatch.setattr(cli.registry, "load_all", lambda: [])
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    rc = cli.main(["--repo", str(tmp_path), "--pr-labels", "release:patch"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "policy-check: warning:" in captured.err
    assert "release:patch" in captured.err
    assert "Engine: policy-check 1.0.10 (installed package)" in captured.out


def test_cli_main_report_includes_engine_header_on_pass(monkeypatch, tmp_path, capsys):
    _write_repo(tmp_path, "1.0.15")
    monkeypatch.setattr(cli.prc, "load_pr_meta", lambda: {})
    monkeypatch.setattr(engine_gate, "_installed_version", lambda: "1.0.15")
    monkeypatch.setattr(cli.registry, "load_all", lambda: [])
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    rc = cli.main(["--repo", str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Engine: policy-check 1.0.15 (installed package)" in out
