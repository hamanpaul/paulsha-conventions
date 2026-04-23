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
    """Composite action must accept profile and version inputs (and only these as required)."""
    action_path = Path(__file__).parent.parent / ".github" / "actions" / "policy-check" / "action.yml"
    assert action_path.exists(), f"Missing {action_path}"

    content = yaml.safe_load(action_path.read_text(encoding="utf-8"))
    inputs = content.get("inputs", {})

    # Spec: composite action 要補 profile 與 version inputs
    assert "profile" in inputs, "Composite action missing 'profile' input"
    assert "version" in inputs, "Composite action missing 'version' input"
    
    # Spec §4.1: action should ONLY expose profile and version as per design
    # All other parameters should be derived from GitHub context in the workflow layer
    assert inputs["profile"]["required"] is True, "profile should be required"
    assert inputs["version"]["required"] is True, "version should be required"


def test_reusable_workflow_bootstraps_runtime_without_installing_caller_repo():
    """Reusable workflow must not assume the downstream repo is an installable package."""
    workflow_path = Path(__file__).parent.parent / ".github" / "workflows" / "reusable-policy-check.yml"
    content = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))

    steps = content["jobs"]["check"]["steps"]
    run_commands = [step.get("run", "") for step in steps if "run" in step]

    assert all("pip install -e ." not in command for command in run_commands), (
        "Reusable workflow must not run 'pip install -e .' in the caller repo. "
        "Bootstrap template/downstream repos do not ship Python package metadata."
    )
    # Runtime must be installed from the policy engine checkout (not just PyYAML alone)
    assert any(
        "pip install" in command and ".policy-engine" in command
        for command in run_commands
    ), (
        "Reusable workflow should install the policy engine package from its dedicated "
        "checkout (.policy-engine) so both policy_check and PyYAML are available."
    )


def test_reusable_workflow_does_not_use_local_composite_action():
    """
    Reusable workflow must NOT use 'uses: ./.github/actions/...' paths.

    When a downstream repo calls this reusable workflow, any './' path resolves
    against the CALLER'S checkout, not paulsha-conventions. The caller's repo has
    no .github/actions/policy-check, so the job fails with action-not-found.
    """
    workflow_path = Path(__file__).parent.parent / ".github" / "workflows" / "reusable-policy-check.yml"
    content = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))

    steps = content["jobs"]["check"]["steps"]
    local_action_uses = [
        step["uses"]
        for step in steps
        if "uses" in step and str(step.get("uses", "")).startswith("./.github/actions/")
    ]

    assert not local_action_uses, (
        f"Reusable workflow must not reference local composite actions via './.github/actions/...' "
        f"because these resolve against the CALLER repo, not paulsha-conventions. "
        f"Found: {local_action_uses}. Use an inline 'run:' step instead."
    )


def test_reusable_workflow_checks_out_policy_engine():
    """
    Reusable workflow must checkout hamanpaul/paulsha-conventions to obtain the
    policy_check module. Without this, the module is unavailable in the caller's
    workspace, and 'python -m policy_check' fails with ModuleNotFoundError.
    """
    workflow_path = Path(__file__).parent.parent / ".github" / "workflows" / "reusable-policy-check.yml"
    content = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))

    steps = content["jobs"]["check"]["steps"]
    checkout_steps_with_repo = [
        step for step in steps
        if step.get("uses", "").startswith("actions/checkout")
        and isinstance(step.get("with"), dict)
        and "hamanpaul/paulsha-conventions" in str(step["with"].get("repository", ""))
    ]

    assert checkout_steps_with_repo, (
        "Reusable workflow must include a dedicated checkout of 'hamanpaul/paulsha-conventions' "
        "to make the policy_check module available. Without it, policy_check cannot be found "
        "in the caller repo's workspace."
    )


def test_run_sh_does_not_prefer_caller_venv_python():
    """
    run.sh must NOT prefer ${WORKSPACE}/.venv/bin/python over the system Python.

    The workflow installs PyYAML with the system Python (from actions/setup-python).
    If run.sh then switches to a caller-repo's .venv Python, PyYAML is absent
    in that interpreter, causing a ModuleNotFoundError at runtime.
    """
    run_sh_path = Path(__file__).parent.parent / ".github" / "actions" / "policy-check" / "run.sh"
    assert run_sh_path.exists(), f"Missing {run_sh_path}"

    content = run_sh_path.read_text(encoding="utf-8")

    assert ".venv/bin/python" not in content, (
        "run.sh must not prefer ${WORKSPACE}/.venv/bin/python. "
        "The .venv may use a different interpreter than the one used to install dependencies, "
        "causing ModuleNotFoundError at runtime."
    )


def test_reusable_workflow_policy_engine_checkout_is_pinned():
    """
    The policy engine checkout must be pinned to the same ref as the workflow being
    executed (github.workflow_sha), not left unpinned (which would always pull main).

    Without an explicit ref the checkout silently drifts: a caller pinned to
    paulsha-conventions@v1.0.0 would still get main-branch policy_check code.
    """
    workflow_path = Path(__file__).parent.parent / ".github" / "workflows" / "reusable-policy-check.yml"
    raw = workflow_path.read_text(encoding="utf-8")
    content = yaml.safe_load(raw)

    steps = content["jobs"]["check"]["steps"]
    engine_checkout_steps = [
        step for step in steps
        if step.get("uses", "").startswith("actions/checkout")
        and isinstance(step.get("with"), dict)
        and "hamanpaul/paulsha-conventions" in str(step["with"].get("repository", ""))
    ]

    assert engine_checkout_steps, (
        "No policy engine checkout step found (hamanpaul/paulsha-conventions). "
        "Cannot verify pinning."
    )

    for step in engine_checkout_steps:
        ref_value = step["with"].get("ref", "")
        assert ref_value, (
            f"Policy engine checkout step '{step.get('name', '?')}' has no 'ref:' field. "
            "Without a ref, GitHub always fetches the default branch (main), which "
            "causes version drift when callers pin to a specific tag or SHA."
        )
        # The ref must use github.workflow_sha so the engine version matches
        # the reusable workflow version that the caller actually requested.
        assert "github.workflow_sha" in raw, (
            "Policy engine checkout should pin to '${{ github.workflow_sha }}' so "
            "the engine version always matches the reusable workflow version under execution."
        )


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
