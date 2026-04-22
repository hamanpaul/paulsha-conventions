"""
Integration tests for composite action fail-close validation.

These tests verify that the action's run.sh actually enforces profile/version
consistency with .paul-project.yml, not just checking for string presence.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import pytest


def test_action_run_sh_fails_on_profile_mismatch():
    """
    Integration test: run.sh should exit non-zero when profile mismatches.
    
    This is a real integration test that executes run.sh with mismatched
    profile/version and verifies fail-close behavior.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "test-repo"
        repo_path.mkdir()
        
        # Create .paul-project.yml with specific profile/version
        config = repo_path / ".paul-project.yml"
        config.write_text("""
policy_profile: flat
policy_version: 1.0.0
""")
        
        # Get path to run.sh
        run_sh = Path(__file__).parent.parent / ".github" / "actions" / "policy-check" / "run.sh"
        assert run_sh.exists(), f"run.sh not found at {run_sh}"
        
        # Run with MISMATCHED profile (expect flat, provide stage-driven)
        result = subprocess.run(
            ["bash", str(run_sh), "stage-driven", "1.0.0"],
            capture_output=True,
            text=True,
            cwd=repo_path,
            env={**os.environ, "GITHUB_WORKSPACE": str(repo_path)},
        )
        
        # Should fail with non-zero exit
        assert result.returncode != 0, (
            f"Expected non-zero exit on profile mismatch, got {result.returncode}. "
            f"stderr: {result.stderr}"
        )
        
        # Should have clear error message
        assert "profile mismatch" in result.stderr.lower() or "ERROR" in result.stderr, (
            f"Expected clear error message in stderr. Got: {result.stderr}"
        )


def test_action_run_sh_fails_on_version_mismatch():
    """Integration test: run.sh should exit non-zero when version mismatches."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "test-repo"
        repo_path.mkdir()
        
        config = repo_path / ".paul-project.yml"
        config.write_text("""
policy_profile: flat
policy_version: 1.0.0
""")
        
        run_sh = Path(__file__).parent.parent / ".github" / "actions" / "policy-check" / "run.sh"
        
        # Run with MISMATCHED version
        result = subprocess.run(
            ["bash", str(run_sh), "flat", "2.0.0"],
            capture_output=True,
            text=True,
            cwd=repo_path,
            env={**os.environ, "GITHUB_WORKSPACE": str(repo_path)},
        )
        
        assert result.returncode != 0, (
            f"Expected non-zero exit on version mismatch, got {result.returncode}"
        )
        assert "version mismatch" in result.stderr.lower() or "ERROR" in result.stderr, (
            f"Expected clear error message. Got: {result.stderr}"
        )


def test_action_run_sh_succeeds_on_match():
    """
    Integration test: run.sh should succeed when profile/version match.
    
    Note: This will try to run policy_check, which may fail for other reasons
    (missing files, etc.), but the validation step should pass.
    We check that it doesn't fail on the validation step specifically.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "test-repo"
        repo_path.mkdir()
        
        config = repo_path / ".paul-project.yml"
        config.write_text("""
policy_profile: flat
policy_version: 1.0.0
""")
        
        run_sh = Path(__file__).parent.parent / ".github" / "actions" / "policy-check" / "run.sh"
        
        # Run with MATCHING profile/version
        result = subprocess.run(
            ["bash", str(run_sh), "flat", "1.0.0"],
            capture_output=True,
            text=True,
            cwd=repo_path,
            env={**os.environ, "GITHUB_WORKSPACE": str(repo_path)},
        )
        
        # Should NOT fail on validation (may fail on policy_check execution, that's OK)
        # The key is: no "profile mismatch" or "version mismatch" error
        assert "profile mismatch" not in result.stderr.lower(), (
            f"Should not report profile mismatch when they match. stderr: {result.stderr}"
        )
        assert "version mismatch" not in result.stderr.lower(), (
            f"Should not report version mismatch when they match. stderr: {result.stderr}"
        )
        # If validation failed, it should say so explicitly
        assert "Profile/version validation failed" not in result.stderr, (
            f"Validation should pass when profile/version match. stderr: {result.stderr}"
        )
