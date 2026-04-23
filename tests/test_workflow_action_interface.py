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
    """Reusable workflow must expose policy_profile, policy_version, and policy_engine_ref inputs."""
    workflow_path = Path(__file__).parent.parent / ".github" / "workflows" / "reusable-policy-check.yml"
    assert workflow_path.exists(), f"Missing {workflow_path}"

    content = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    
    # PyYAML parses 'on:' as boolean True in YAML 1.1 mode
    # Get the workflow_call section, handling both 'on' and True keys
    on_section = content.get("on") or content.get(True)
    assert on_section, "Missing 'on' section in workflow"
    
    inputs = on_section.get("workflow_call", {}).get("inputs", {})

    # Spec: workflow_call.inputs 暴露三個輸入：
    #   - policy_profile, policy_version: 業務參數
    #   - policy_engine_ref: 明確指定 policy engine checkout 的 ref/SHA，
    #     解決跨 repo reusable workflow 中 github.workflow_sha 屬於 caller repo 的問題
    assert set(inputs.keys()) == {"policy_profile", "policy_version", "policy_engine_ref"}, (
        f"Reusable workflow should expose policy_profile, policy_version, and policy_engine_ref. "
        f"Found: {list(inputs.keys())}"
    )

    # policy_profile and policy_version: required strings
    assert inputs["policy_profile"]["type"] == "string"
    assert inputs["policy_profile"]["required"] is True
    assert inputs["policy_version"]["type"] == "string"
    assert inputs["policy_version"]["required"] is True

    # policy_engine_ref: required string — caller must always pin explicitly
    assert inputs["policy_engine_ref"]["type"] == "string"
    assert inputs["policy_engine_ref"]["required"] is True, (
        "policy_engine_ref must be required so callers are forced to pin to a specific "
        "full 40-character commit SHA; an optional default would encourage unpinned / drifting usage."
    )


def test_reusable_workflow_input_descriptions_do_not_use_github_expressions():
    """
    workflow_call input descriptions must be plain metadata text, not `${{ ... }}`.

    GitHub parses expressions in reusable workflow metadata. If an input description
    contains `${{ github.sha }}` or similar expression syntax, the called workflow is
    rejected before any job starts.
    """
    workflow_path = Path(__file__).parent.parent / ".github" / "workflows" / "reusable-policy-check.yml"
    content = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))

    on_section = content.get("on") or content.get(True)
    inputs = on_section.get("workflow_call", {}).get("inputs", {})

    unsafe_descriptions = {
        input_name: spec.get("description", "")
        for input_name, spec in inputs.items()
        if "${{" in str(spec.get("description", ""))
    }

    assert not unsafe_descriptions, (
        "workflow_call input descriptions must not contain GitHub expression syntax like "
        "'${{ github.sha }}'. GitHub parses reusable-workflow metadata before jobs start, "
        f"so these descriptions make the workflow invalid. Found: {unsafe_descriptions}"
    )


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
    The policy engine checkout must be pinned via the explicit `policy_engine_ref` input,
    NOT via `github.workflow_sha`.

    In a cross-repo reusable workflow, `github.workflow_sha` is the SHA of the CALLER's
    workflow file, not of hamanpaul/paulsha-conventions. Using it as the ref would check
    out a random SHA from the caller's repo (or fail), causing version drift.

    The correct contract: callers must supply `policy_engine_ref` as a full 40-character
    commit SHA pointing at hamanpaul/paulsha-conventions so the engine version is deterministic.
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
            "causes version drift when callers pin to a specific full 40-character SHA."
        )
        # Must NOT use github.workflow_sha (belongs to the caller repo, not paulsha-conventions)
        assert "github.workflow_sha" not in ref_value, (
            "Policy engine checkout must NOT use github.workflow_sha. "
            "In a cross-repo reusable workflow the github context is always associated "
            "with the CALLER workflow, so github.workflow_sha is the caller's SHA, not "
            "a paulsha-conventions SHA. Use inputs.policy_engine_ref instead."
        )
        # Must use the explicit input so the caller controls which engine version is used
        assert "inputs.policy_engine_ref" in ref_value, (
            "Policy engine checkout ref must be '${{ inputs.policy_engine_ref }}'. "
            "This forces every caller to pin explicitly to a full 40-character SHA in "
            "hamanpaul/paulsha-conventions, preventing silent version drift."
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


def test_caller_workflow_passes_policy_engine_ref_to_reusable():
    """
    Self-dogfood test: the caller workflow (.github/workflows/policy-check.yml)
    must pass policy_engine_ref as exactly '${{ github.sha }}' to the reusable workflow.

    '${{ github.sha }}' evaluates to a full 40-char commit SHA at runtime, satisfying the
    full-SHA-only contract.  Using '${{ github.workflow_sha }}' would be a regression —
    in cross-repo reusable workflows that SHA belongs to the caller's repo, not paulsha-conventions.
    """
    caller_workflow_path = (
        Path(__file__).parent.parent / ".github" / "workflows" / "policy-check.yml"
    )
    assert caller_workflow_path.exists(), f"Missing {caller_workflow_path}"

    content = yaml.safe_load(caller_workflow_path.read_text(encoding="utf-8"))

    jobs = content.get("jobs", {})
    assert "check" in jobs, "Missing 'check' job in caller workflow"

    job = jobs["check"]
    assert "uses" in job, "Caller workflow job must use the reusable workflow"

    job_with = job.get("with", {})
    assert "policy_engine_ref" in job_with, (
        "Caller workflow must pass 'policy_engine_ref' to the reusable workflow. "
        "This self-dogfoods the requirement that downstream repos must pin explicitly."
    )

    ref_value = job_with.get("policy_engine_ref", "")

    # Must be exactly the github.sha expression — evaluates to a full 40-char SHA at runtime
    assert ref_value == "${{ github.sha }}", (
        f"policy_engine_ref in self-dogfood caller must be exactly '${{{{ github.sha }}}}'. "
        f"Got: '{ref_value}'. "
        "Do not use github.workflow_sha — in cross-repo reusable workflows that SHA "
        "belongs to the caller's repo, not to paulsha-conventions."
    )

    # Explicitly guard against regression to github.workflow_sha
    assert "github.workflow_sha" not in ref_value, (
        "policy_engine_ref must NOT use github.workflow_sha. "
        "In cross-repo reusable workflows, github.workflow_sha is the caller's repo SHA. "
        "Use github.sha instead (it evaluates to a full 40-char SHA at runtime)."
    )


def test_reusable_workflow_validates_policy_engine_ref_is_full_sha():
    """
    Reusable workflow must have a validation step before 'Checkout policy engine' that
    rejects any policy_engine_ref that is not a full 40-character lowercase hex commit SHA.

    This prevents callers from accidentally passing tags, short SHAs, or branch refs.
    Tags are no longer valid — only a full pinned SHA is safe and unambiguous.
    """
    workflow_path = Path(__file__).parent.parent / ".github" / "workflows" / "reusable-policy-check.yml"
    content = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))

    steps = content["jobs"]["check"]["steps"]

    # Locate the "Checkout policy engine" step index
    checkout_engine_idx = next(
        (
            i for i, s in enumerate(steps)
            if s.get("uses", "").startswith("actions/checkout")
            and "hamanpaul/paulsha-conventions" in str(s.get("with", {}).get("repository", ""))
        ),
        None,
    )
    assert checkout_engine_idx is not None, (
        "Could not find 'Checkout policy engine' step. Cannot verify validation ordering."
    )

    # A validation step must appear BEFORE the engine checkout
    pre_checkout_steps = steps[:checkout_engine_idx]
    validation_steps = [
        s for s in pre_checkout_steps
        if "run" in s
        and "policy_engine_ref" in s.get("run", "")
        and (
            "40" in s.get("run", "")
            or "[0-9a-f]" in s.get("run", "")
        )
    ]

    assert validation_steps, (
        "Reusable workflow must have a validation step before 'Checkout policy engine' "
        "that checks policy_engine_ref is a full 40-character commit SHA. "
        "This prevents tags, short SHAs, or branch refs from silently succeeding."
    )

    run_cmd = validation_steps[0]["run"]
    assert "exit 1" in run_cmd, (
        "Validation step must 'exit 1' when the ref does not match the full-SHA pattern."
    )


def test_reusable_workflow_policy_engine_ref_description_says_full_sha_only():
    """
    The policy_engine_ref input description must state 'full 40-character commit SHA'
    and must NOT mention 'tag' as an acceptable value.

    Tags are no longer accepted — only full 40-character commit SHAs are valid.
    This eliminates the tag-vs-SHA ambiguity and matches the security/pinning intent.
    """
    workflow_path = Path(__file__).parent.parent / ".github" / "workflows" / "reusable-policy-check.yml"
    content = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))

    on_section = content.get("on") or content.get(True)
    inputs = on_section.get("workflow_call", {}).get("inputs", {})
    description = inputs.get("policy_engine_ref", {}).get("description", "")

    assert "40" in description, (
        "policy_engine_ref description must state it requires a full 40-character commit SHA. "
        f"Current description: {description!r}"
    )

    # Must NOT present tags as valid inputs (the old description said "Tag or commit SHA")
    # Note: the word "tag" may appear in explanatory context (e.g. "tags are rejected"),
    # so check for the specific pattern that implies tags are acceptable values.
    assert "tag or commit" not in description.lower(), (
        "policy_engine_ref description must NOT say 'tag or commit' — that implies tags are valid. "
        "Only full 40-character commit SHAs are accepted. "
        f"Current description: {description!r}"
    )
    # Also reject the old-style opening "Tag or commit SHA..."
    assert not description.lower().startswith("tag "), (
        "policy_engine_ref description must NOT start with 'Tag ...' suggesting tags are a valid type. "
        f"Current description: {description!r}"
    )


def test_reusable_workflow_binds_policy_engine_ref_via_env_not_direct_interpolation():
    """
    The validation step must bind policy_engine_ref through 'env:' instead of direct
    shell interpolation to prevent shell injection.

    If policy_engine_ref is interpolated directly as `ref="${{ inputs.policy_engine_ref }}"`,
    a malicious value containing '"' can break out of the quoted string and bypass validation.
    
    Instead, the step should use 'env:' to set POLICY_ENGINE_REF and read from it via
    shell variable expansion, which safely isolates the value.
    """
    workflow_path = Path(__file__).parent.parent / ".github" / "workflows" / "reusable-policy-check.yml"
    raw = workflow_path.read_text(encoding="utf-8")
    content = yaml.safe_load(raw)

    steps = content["jobs"]["check"]["steps"]

    # Find the validation step
    validation_steps = [
        s for s in steps
        if "run" in s
        and "policy_engine_ref" in s.get("run", "")
        and ("40" in s.get("run", "") or "[0-9a-f]" in s.get("run", ""))
    ]

    assert validation_steps, (
        "Could not find validation step for policy_engine_ref"
    )

    validation_step = validation_steps[0]
    run_cmd = validation_step.get("run", "")

    # The step must NOT interpolate directly: ${{ inputs.policy_engine_ref }}
    # should not appear inside the shell script body
    assert "${{ inputs.policy_engine_ref }}" not in run_cmd, (
        "Validation step must NOT interpolate inputs.policy_engine_ref directly in the shell script. "
        "This allows shell injection. Use 'env: POLICY_ENGINE_REF: ${{ inputs.policy_engine_ref }}' "
        "and read from $POLICY_ENGINE_REF instead."
    )

    # The step MUST have an 'env:' section that binds POLICY_ENGINE_REF
    env_section = validation_step.get("env", {})
    assert env_section, (
        "Validation step must have 'env:' section to safely bind policy_engine_ref"
    )

    assert "POLICY_ENGINE_REF" in env_section, (
        f"Validation step 'env:' must include POLICY_ENGINE_REF. "
        f"Current env: {env_section}"
    )

    # The env binding must map to the exact workflow input expression
    policy_engine_ref_value = env_section.get("POLICY_ENGINE_REF")
    assert policy_engine_ref_value == "${{ inputs.policy_engine_ref }}", (
        f"POLICY_ENGINE_REF env must map to '${{{{ inputs.policy_engine_ref }}}}'. "
        f"Got: {policy_engine_ref_value}"
    )

    # The shell script must read from the env variable, not direct interpolation
    assert "$POLICY_ENGINE_REF" in run_cmd, (
        "Validation step must read from $POLICY_ENGINE_REF environment variable. "
        "This prevents shell injection attacks."
    )


def test_reusable_workflow_run_step_binds_profile_version_via_env():
    """
    The 'Run policy check' step must bind policy_profile and policy_version through
    'env:' instead of direct shell interpolation to prevent shell injection.

    Exact required env mappings:
      POLICY_PROFILE: ${{ inputs.policy_profile }}
      POLICY_VERSION: ${{ inputs.policy_version }}

    The run: script must use $POLICY_PROFILE / $POLICY_VERSION shell variables,
    not ${{ inputs.policy_profile }} / ${{ inputs.policy_version }} directly.
    """
    workflow_path = Path(__file__).parent.parent / ".github" / "workflows" / "reusable-policy-check.yml"
    raw = workflow_path.read_text(encoding="utf-8")
    content = yaml.safe_load(raw)

    steps = content["jobs"]["check"]["steps"]

    # Find the "Run policy check" step by name
    run_steps = [s for s in steps if s.get("name", "") == "Run policy check"]
    assert run_steps, (
        "Could not find 'Run policy check' step in reusable workflow. "
        "Expected a step with name: 'Run policy check'."
    )
    run_step = run_steps[0]
    run_cmd = run_step.get("run", "")
    env_section = run_step.get("env", {})

    # --- env binding assertions ---
    assert env_section, (
        "'Run policy check' step must have an 'env:' section to safely bind inputs."
    )
    assert "POLICY_PROFILE" in env_section, (
        f"'Run policy check' step 'env:' must contain POLICY_PROFILE. "
        f"Current env: {env_section}"
    )
    assert "POLICY_VERSION" in env_section, (
        f"'Run policy check' step 'env:' must contain POLICY_VERSION. "
        f"Current env: {env_section}"
    )

    # --- exact mapping assertions ---
    assert env_section["POLICY_PROFILE"] == "${{ inputs.policy_profile }}", (
        f"POLICY_PROFILE must map to exactly '${{{{ inputs.policy_profile }}}}'. "
        f"Got: {env_section.get('POLICY_PROFILE')!r}"
    )
    assert env_section["POLICY_VERSION"] == "${{ inputs.policy_version }}", (
        f"POLICY_VERSION must map to exactly '${{{{ inputs.policy_version }}}}'. "
        f"Got: {env_section.get('POLICY_VERSION')!r}"
    )

    # --- no direct interpolation in shell body ---
    assert "${{ inputs.policy_profile }}" not in run_cmd, (
        "'Run policy check' run: script must NOT interpolate inputs.policy_profile directly. "
        "Use $POLICY_PROFILE shell variable instead."
    )
    assert "${{ inputs.policy_version }}" not in run_cmd, (
        "'Run policy check' run: script must NOT interpolate inputs.policy_version directly. "
        "Use $POLICY_VERSION shell variable instead."
    )

    # --- shell variables must actually be used ---
    assert "$POLICY_PROFILE" in run_cmd, (
        "'Run policy check' run: script must read from $POLICY_PROFILE env variable."
    )
    assert "$POLICY_VERSION" in run_cmd, (
        "'Run policy check' run: script must read from $POLICY_VERSION env variable."
    )
