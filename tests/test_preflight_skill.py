from __future__ import annotations

import os
import shutil
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
    assert 'runpy.run_module("policy_check.preflight"' in text
    assert '"$PYTHON_BIN" -I -B -c' in text
    assert "PYTHONPATH=" not in text
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


def test_preflight_skill_wrapper_prefers_canonical_over_target_decoy(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    subprocess.run(["git", "init", "-q", str(target)], check=True)
    decoy = target / "policy_check"
    decoy.mkdir()
    (decoy / "__init__.py").write_text("", encoding="utf-8")
    (decoy / "preflight.py").write_text(
        'print("decoy module loaded")\n',
        encoding="utf-8",
    )

    env = dict(os.environ)
    env["PSC_PREFLIGHT_PYTHON"] = sys.executable
    result = subprocess.run(
        [str(SKILL / "scripts" / "preflight.sh"), "--help"],
        cwd=target,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("usage: policy-preflight")
    assert "decoy module loaded" not in result.stdout


def test_preflight_skill_wrapper_ignores_ambient_pythonpath(tmp_path: Path) -> None:
    evil = tmp_path / "evil"
    evil.mkdir()
    (evil / "yaml.py").write_text(
        'raise RuntimeError("ambient PYTHONPATH loaded")\n',
        encoding="utf-8",
    )
    env = dict(os.environ)
    env["PSC_PREFLIGHT_PYTHON"] = sys.executable
    env["PYTHONPATH"] = str(evil)

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
    assert "ambient PYTHONPATH loaded" not in result.stderr


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


def test_deployed_skill_delegates_to_stable_runtime_launcher(tmp_path: Path) -> None:
    deployed_skill = tmp_path / "deployed" / "skills" / "preflight-ci"
    shutil.copytree(SKILL, deployed_skill)
    runtime_root = tmp_path / "runtime"
    launcher = runtime_root / "bin" / "policy-preflight"
    launcher.parent.mkdir(parents=True)
    launcher.write_text(
        "#!/usr/bin/env bash\n"
        "set -eu\n"
        'printf "%s\\n" "$PWD" "$@"\n',
        encoding="utf-8",
    )
    launcher.chmod(0o755)
    target = tmp_path / "target"
    target.mkdir()
    subprocess.run(["git", "init", "-q", str(target)], check=True)
    nested = target / "nested"
    nested.mkdir()
    env = dict(os.environ)
    env["PSC_CONVENTIONS_ROOT"] = str(runtime_root)
    result = subprocess.run(
        [str(deployed_skill / "scripts" / "preflight.sh"), "--offline"],
        cwd=nested,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        str(nested),
        "--repo",
        str(target),
        "--offline",
    ]


def test_deployed_skill_derives_custom_runtime_root_from_physical_location(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "custom-runtime"
    deployed_skill = (
        runtime_root
        / "releases"
        / "1.0.14"
        / "artifact"
        / "skills"
        / "preflight-ci"
    )
    shutil.copytree(SKILL, deployed_skill)
    (runtime_root / "current").symlink_to(
        runtime_root / "releases" / "1.0.14"
    )
    launcher = runtime_root / "bin" / "policy-preflight"
    launcher.parent.mkdir(parents=True)
    launcher.write_text(
        "#!/usr/bin/env bash\n"
        "set -eu\n"
        'printf "%s\\n" "$@"\n',
        encoding="utf-8",
    )
    launcher.chmod(0o755)
    skill_link = tmp_path / "home" / ".agents" / "skills" / "preflight-ci"
    skill_link.parent.mkdir(parents=True)
    skill_link.symlink_to(deployed_skill)
    target = tmp_path / "target"
    target.mkdir()
    subprocess.run(["git", "init", "-q", str(target)], check=True)
    env = dict(os.environ)
    env["PSC_CONVENTIONS_ROOT"] = str(tmp_path / "wrong-runtime")
    env.pop("XDG_DATA_HOME", None)
    env["HOME"] = str(tmp_path / "wrong-home")

    result = subprocess.run(
        [str(skill_link / "scripts" / "preflight.sh"), "--offline"],
        cwd=target,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "--repo",
        str(target),
        "--offline",
    ]


def test_installer_rejects_non_symlink_target(tmp_path) -> None:
    target_root = tmp_path / "skills"
    target_root.mkdir()
    target = target_root / "preflight-ci"
    target.mkdir()
    (target / "sentinel.txt").write_text("keep", encoding="utf-8")

    installer = REPO / "scripts" / "install-preflight-skill.sh"
    result = subprocess.run(
        [str(installer), "--target-root", str(target_root)],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1, result.stderr
    assert target.is_dir()
    assert (target / "sentinel.txt").read_text(encoding="utf-8") == "keep"


def test_installer_rejects_wrong_symlink_without_replace(tmp_path) -> None:
    target_root = tmp_path / "skills"
    target_root.mkdir()
    other = tmp_path / "other-target"
    other.mkdir()
    target = target_root / "preflight-ci"
    target.symlink_to(other)

    installer = REPO / "scripts" / "install-preflight-skill.sh"
    result = subprocess.run(
        [str(installer), "--target-root", str(target_root)],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1, result.stderr
    assert target.is_symlink()
    assert target.resolve() == other.resolve()


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


def test_installer_requires_explicit_flag_to_replace_managed_runtime_skill(
    tmp_path: Path,
) -> None:
    target_root = tmp_path / "skills"
    target_root.mkdir()
    managed = (
        tmp_path
        / "runtime"
        / "current"
        / "artifact"
        / "skills"
        / "preflight-ci"
    )
    managed.mkdir(parents=True)
    target = target_root / "preflight-ci"
    target.symlink_to(managed)
    installer = REPO / "scripts" / "install-preflight-skill.sh"

    refused = subprocess.run(
        [
            str(installer),
            "--target-root",
            str(target_root),
            "--replace",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert refused.returncode == 1
    assert "managed by a runtime bundle" in refused.stderr
    assert target.resolve() == managed.resolve()

    migrated = subprocess.run(
        [
            str(installer),
            "--target-root",
            str(target_root),
            "--replace-managed-runtime",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert migrated.returncode == 0, migrated.stderr
    assert target.resolve() == SKILL.resolve()
