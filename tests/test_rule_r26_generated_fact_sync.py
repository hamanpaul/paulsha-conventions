from __future__ import annotations

from pathlib import Path

from policy_check import config as cfg
from policy_check.rules import registry
from policy_check.rules.base import RuleContext, Status


def _write(repo: Path, rel: str, text: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _cfg_text(extra: str = "") -> str:
    return "policy_profile: flat\npolicy_version: 1.0.7\n" + extra


def get_rule():
    loaded = {r.rule_id: r for r in registry.load_all()}
    assert "R-26" in loaded, "R-26 is not registered"
    return loaded["R-26"]


def make_ctx(repo: Path, *, labels: list[str] | None = None) -> RuleContext:
    return RuleContext(
        repo_root=repo,
        profile="flat",
        policy_version="1.0.7",
        config=cfg.load(repo),
        pr_labels=labels or [],
    )


_GEN = "print('alpha')\nprint('beta')\n"

_CFG = (
    "generated_facts:\n"
    "  - kind: fact_list\n"
    "    command: \"python3 gen.py\"\n"
    "    reflected_in: README.md\n"
    "    marker: rpc\n"
)


def _marker_block(content: str) -> str:
    return (
        "<!-- BEGIN: generated-fact marker=\"rpc\" -->\n"
        f"{content}\n"
        "<!-- END: generated-fact marker=\"rpc\" -->\n"
    )


def test_r26_not_applicable_passes(tmp_path):
    _write(tmp_path, ".paul-project.yml", _cfg_text())
    assert get_rule().check(make_ctx(tmp_path)).status == Status.PASS


def test_r26_in_sync_passes(tmp_path):
    _write(tmp_path, ".paul-project.yml", _cfg_text(_CFG))
    _write(tmp_path, "gen.py", _GEN)
    _write(tmp_path, "README.md", "# docs\n\n" + _marker_block("alpha\nbeta"))
    assert get_rule().check(make_ctx(tmp_path)).status == Status.PASS


def test_r26_output_mismatch_fails(tmp_path):
    _write(tmp_path, ".paul-project.yml", _cfg_text(_CFG))
    _write(tmp_path, "gen.py", _GEN)
    _write(tmp_path, "README.md", "# docs\n\n" + _marker_block("alpha\ngamma"))
    res = get_rule().check(make_ctx(tmp_path))
    assert res.status == Status.FAIL


def test_r26_missing_marker_fails(tmp_path):
    _write(tmp_path, ".paul-project.yml", _cfg_text(_CFG))
    _write(tmp_path, "gen.py", _GEN)
    _write(tmp_path, "README.md", "# docs\n\nno marker here\n")
    res = get_rule().check(make_ctx(tmp_path))
    assert res.status == Status.FAIL


def test_r26_command_nonzero_fails(tmp_path):
    _write(tmp_path, ".paul-project.yml", _cfg_text(_CFG))
    _write(tmp_path, "gen.py", "import sys\nsys.exit(2)\n")
    _write(tmp_path, "README.md", "# docs\n\n" + _marker_block("alpha\nbeta"))
    res = get_rule().check(make_ctx(tmp_path))
    assert res.status == Status.FAIL


def test_r26_malformed_config_fails(tmp_path):
    extra = (
        "generated_facts:\n"
        "  - kind: fact_list\n"
        "    reflected_in: README.md\n"  # missing command + marker
    )
    _write(tmp_path, ".paul-project.yml", _cfg_text(extra))
    _write(tmp_path, "README.md", "# docs\n")
    res = get_rule().check(make_ctx(tmp_path))
    assert res.status == Status.FAIL


def test_r26_coexists_with_cli_help_marker(tmp_path):
    # A generated-fact block and an unrelated cli-help block live in the same doc;
    # R-26 only validates the generated-fact block and ignores the cli-help one.
    _write(tmp_path, ".paul-project.yml", _cfg_text(_CFG))
    _write(tmp_path, "gen.py", _GEN)
    cli_block = (
        "<!-- BEGIN: cli-help marker=\"app\" -->\n"
        "stale unrelated help text\n"
        "<!-- END: cli-help marker=\"app\" -->\n"
    )
    _write(tmp_path, "README.md", "# docs\n\n" + cli_block + "\n" + _marker_block("alpha\nbeta"))
    assert get_rule().check(make_ctx(tmp_path)).status == Status.PASS
