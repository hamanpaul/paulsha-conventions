from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from policy_check import cli


def _write_repo(tmp_path: Path) -> None:
    (tmp_path / ".paul-project.yml").write_text(
        "policy_profile: flat\npolicy_version: 1.0.3\ntier: work\n", encoding="utf-8"
    )


def _build_ctx(tmp_path: Path, **overrides) -> Namespace:
    base = Namespace(
        repo=str(tmp_path),
        pr_title=None,
        pr_body=None,
        pr_labels=None,
        pr_base_ref=None,
        pr_head_ref=None,
        repo_visibility=None,
        only=None,
    )
    base.__dict__.update(overrides)
    return base


def test_build_context_prefers_provider_visibility_over_cli(monkeypatch, tmp_path):
    _write_repo(tmp_path)
    monkeypatch.setattr(
        cli.prc,
        "load_pr_meta",
        lambda: {
            "provider": "github",
            "repo_visibility": "private",
            "pr_labels": [],
            "pr_base_ref": "main",
            "pr_head_ref": "feature/x",
            "pr_base_sha": None,
        },
    )
    args = _build_ctx(tmp_path, repo_visibility="public")
    ctx = cli.build_context(args)
    assert ctx.repo_visibility == "private"


def test_build_context_falls_back_to_cli_visibility(monkeypatch, tmp_path):
    _write_repo(tmp_path)
    monkeypatch.setattr(cli.prc, "load_pr_meta", lambda: {})
    args = _build_ctx(tmp_path, repo_visibility="internal")
    ctx = cli.build_context(args)
    assert ctx.repo_visibility == "internal"


def test_build_context_defaults_unknown(monkeypatch, tmp_path):
    _write_repo(tmp_path)
    monkeypatch.setattr(cli.prc, "load_pr_meta", lambda: {})
    args = _build_ctx(tmp_path)
    ctx = cli.build_context(args)
    assert ctx.repo_visibility == "unknown"
