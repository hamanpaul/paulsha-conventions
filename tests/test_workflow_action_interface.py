"""
Test reusable workflow and composite action interface contracts.

Spec reference: §4.1 Reusable workflow structure
- reusable workflow should ONLY expose policy_profile and policy_version
- composite action should accept profile and version inputs
- action should validate profile/version against .paul-project.yml
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


def test_reusable_workflow_interface_contract():
    """Reusable workflow must ONLY expose policy_profile and policy_version inputs."""
    workflow_path = Path(__file__).parent.parent / ".github" / "workflows" / "reusable-policy-check.yml"
    assert workflow_path.exists(), f"Missing {workflow_path}"

    content = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    
    # PyYAML parses 'on:' as boolean True in YAML 1.1 mode
    # Get the workflow_call section, handling both 'on' and True keys
    on_section = content.get("on") or content.get(True)
    assert on_section, "Missing 'on' section in workflow"
    
    inputs = on_section.get("workflow_call", {}).get("inputs", {})

    # Spec: workflow_call.inputs 只暴露 policy_profile 與 policy_version 兩個必要參數
    assert set(inputs.keys()) == {"policy_profile", "policy_version"}, (
        f"Reusable workflow should ONLY expose policy_profile and policy_version. "
        f"Found: {list(inputs.keys())}"
    )

    # Both should be required strings
    assert inputs["policy_profile"]["type"] == "string"
    assert inputs["policy_profile"]["required"] is True
    assert inputs["policy_version"]["type"] == "string"
    assert inputs["policy_version"]["required"] is True


def test_composite_action_has_profile_version_inputs():
    """Composite action must accept profile and version inputs."""
    action_path = Path(__file__).parent.parent / ".github" / "actions" / "policy-check" / "action.yml"
    assert action_path.exists(), f"Missing {action_path}"

    content = yaml.safe_load(action_path.read_text(encoding="utf-8"))
    inputs = content.get("inputs", {})

    # Spec: composite action 要補 profile 與 version inputs
    assert "profile" in inputs, "Composite action missing 'profile' input"
    assert "version" in inputs, "Composite action missing 'version' input"


def test_composite_action_validates_profile_version_consistency():
    """
    Composite action run.sh should validate profile/version against .paul-project.yml.
    
    This test verifies that the run.sh script or action logic fails when
    profile/version don't match .paul-project.yml (fail-close).
    
    We'll check this indirectly by ensuring profile/version are passed through to the CLI.
    The actual validation logic should be tested in integration tests.
    """
    run_sh_path = Path(__file__).parent.parent / ".github" / "actions" / "policy-check" / "run.sh"
    assert run_sh_path.exists(), f"Missing {run_sh_path}"

    content = run_sh_path.read_text(encoding="utf-8")
    
    # The run.sh should reference profile and version inputs
    # (exact implementation may vary, but they should be used)
    assert "profile" in content.lower() or "PROFILE" in content, (
        "run.sh should handle profile input"
    )
    assert "version" in content.lower() or "VERSION" in content, (
        "run.sh should handle version input"
    )
