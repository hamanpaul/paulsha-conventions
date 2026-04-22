"""
Tests for scripts/update-cli-help.sh self-dogfood capability.

Verifies that update-cli-help.sh can actually process the current repo's
.paul-project.yml and update markers correctly.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def test_update_cli_help_dry_run_on_self_repo():
    """
    Self-dogfood test: update-cli-help.sh should work on this repo.
    
    Runs in dry-run mode and verifies:
    1. It can parse .paul-project.yml cli entries
    2. It can execute the CLI commands
    3. It can locate marker blocks in README.md
    4. Exit code is 0 (no failures)
    """
    repo_root = Path(__file__).parent.parent
    script = repo_root / "scripts" / "update-cli-help.sh"
    assert script.exists(), f"update-cli-help.sh not found at {script}"
    
    # Run in dry-run mode
    result = subprocess.run(
        ["bash", str(script), "--repo", str(repo_root), "--dry-run"],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    
    # Should succeed
    assert result.returncode == 0, (
        f"update-cli-help.sh --dry-run failed with exit {result.returncode}. "
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    
    # Should mention README.md (the marker file)
    assert "README.md" in result.stdout, (
        f"Expected to see README.md in output. Got: {result.stdout}"
    )
    
    # Should NOT have errors about missing marker
    assert "marker not found" not in result.stderr.lower(), (
        f"Should not report missing markers. stderr: {result.stderr}"
    )
    assert "marker missing" not in result.stderr.lower(), (
        f"Should not report missing markers. stderr: {result.stderr}"
    )


def test_update_cli_help_recognizes_cli_entries():
    """
    Verify update-cli-help.sh actually processes cli entries from config.
    
    Should show it's processing the policy_check command.
    """
    repo_root = Path(__file__).parent.parent
    script = repo_root / "scripts" / "update-cli-help.sh"
    
    result = subprocess.run(
        ["bash", str(script), "--repo", str(repo_root), "--dry-run"],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    
    assert result.returncode == 0
    
    # The output should indicate it processed at least one CLI entry
    # Either by showing "UPDATE" or "UNCHANGED" for a file, or by not reporting 0 entries
    assert "CLI entries: 0" not in result.stdout, (
        "Should find CLI entries in .paul-project.yml"
    )
