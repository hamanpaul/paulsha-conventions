from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "skills" / "preflight-ci"


def test_preflight_skill_is_owned_by_conventions() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "name: preflight-ci" in text
    assert "owned and deployed by paulsha-conventions" in text
    assert "custom-skills" not in text


def test_preflight_skill_wrapper_delegates_without_action_resolution() -> None:
    text = (SKILL / "scripts" / "preflight.sh").read_text(encoding="utf-8")
    assert "-m policy_check.preflight" in text
    assert "--engine-source" in text
    assert "policy-check.yml" not in text
    assert "git clone" not in text
    assert "git fetch" not in text


def test_preflight_skill_wrapper_loads_canonical_help() -> None:
    env = dict(os.environ)
    env["PSC_PREFLIGHT_PYTHON"] = sys.executable
    result = subprocess.run(
        [str(SKILL / "scripts" / "preflight.sh"), "--help"],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("usage: policy-preflight")
    assert "--engine-source" in result.stdout


def test_preflight_skill_wrapper_keeps_target_as_working_directory(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    subprocess.run(["git", "init", "-q", str(target)], check=True)
    (target / "body.md").write_text("PR body\n", encoding="utf-8")

    fake_python = tmp_path / "python"
    fake_python.write_text(
        "#!/usr/bin/env bash\n"
        "set -eu\n"
        "test -r body.md\n"
        'printf "%s\\n" "$PWD"\n',
        encoding="utf-8",
    )
    fake_python.chmod(0o755)

    env = dict(os.environ)
    env["PSC_PREFLIGHT_PYTHON"] = str(fake_python)
    result = subprocess.run(
        [
            str(SKILL / "scripts" / "preflight.sh"),
            "--offline",
            "--pr-body-file",
            "body.md",
        ],
        cwd=target,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(target)


def test_installer_migrates_only_a_symlink(tmp_path) -> None:
    target_root = tmp_path / "skills"
    target_root.mkdir()
    legacy = tmp_path / "legacy-preflight-ci"
    legacy.mkdir()
    target = target_root / "preflight-ci"
    target.symlink_to(legacy)

    installer = REPO / "scripts" / "install-preflight-skill.sh"
    result = subprocess.run(
        [str(installer), "--target-root", str(target_root), "--replace"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert target.resolve() == SKILL.resolve()

    again = subprocess.run(
        [str(installer), "--target-root", str(target_root)],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert again.returncode == 0, again.stderr
