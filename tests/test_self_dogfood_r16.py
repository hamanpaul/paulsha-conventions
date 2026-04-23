"""
Test R-16 self-dogfood requirement.

Spec reference: §4.2 R-16 CLI help sync
- paulsha-conventions repo must have cli: entries in .paul-project.yml
- README.md must have corresponding marker blocks
- R-16 should NOT show "No CLI entries declared"
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


def test_paul_project_yml_has_cli_entries():
    """Self-dogfood: .paul-project.yml must declare cli: entries."""
    config_path = Path(__file__).parent.parent / ".paul-project.yml"
    assert config_path.exists(), "Missing .paul-project.yml"

    content = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    cli_entries = content.get("cli")

    assert cli_entries is not None, (
        "Self-dogfood requirement: .paul-project.yml must have 'cli:' declaration"
    )
    assert isinstance(cli_entries, list), "cli: must be a list"
    assert len(cli_entries) > 0, (
        "Self-dogfood requirement: cli: must have at least one entry (e.g., 'python3 -m policy_check')"
    )


def test_cli_entry_points_to_policy_check_module():
    """Self-dogfood: at least one cli entry should point to 'python3 -m policy_check'."""
    config_path = Path(__file__).parent.parent / ".paul-project.yml"
    content = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    cli_entries = content.get("cli", [])

    # At least one entry should reference policy_check
    policy_check_entries = [
        entry for entry in cli_entries 
        if "policy_check" in entry.get("command", "")
    ]
    
    assert len(policy_check_entries) > 0, (
        "Self-dogfood: at least one cli: entry must point to policy_check module"
    )


def test_readme_has_cli_help_marker():
    """Self-dogfood: README.md must have cli-help marker block for policy_check."""
    config_path = Path(__file__).parent.parent / ".paul-project.yml"
    content = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    cli_entries = content.get("cli", [])

    readme_path = Path(__file__).parent.parent / "README.md"
    assert readme_path.exists(), "Missing README.md"
    
    readme_content = readme_path.read_text(encoding="utf-8")

    # For each cli entry reflected_in README.md, check marker exists
    for entry in cli_entries:
        reflected_in = entry.get("reflected_in", "")
        if "README.md" in reflected_in:
            marker = entry.get("marker")
            assert marker, f"cli entry reflected in README.md must have 'marker' field"
            
            # Check for BEGIN and END markers
            begin_marker = f'<!-- BEGIN: cli-help marker="{marker}" -->'
            end_marker = f'<!-- END: cli-help marker="{marker}" -->'
            
            assert begin_marker in readme_content, (
                f"README.md missing BEGIN marker for {marker}"
            )
            assert end_marker in readme_content, (
                f"README.md missing END marker for {marker}"
            )
