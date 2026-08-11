from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from policy_check import identity as ident
from policy_check.runtime_bundle import builder, integrity, manager


REPO = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    os.environ.get("PACKAGING") != "1",
    reason="runtime bundle packaging smoke requires build and wheel tooling",
)


def _run(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> str:
    result = subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"command failed: {argv[0]}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    return result.stdout.strip()


def _commit_release(repo: Path, previous: str, version: str) -> str:
    (repo / "VERSION").write_text(f"{version}\n", encoding="utf-8")
    pyproject = repo / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    expected = f'version = "{previous}"'
    assert text.count(expected) == 1
    pyproject.write_text(
        text.replace(expected, f'version = "{version}"'),
        encoding="utf-8",
    )
    _run(["git", "add", "VERSION", "pyproject.toml"], cwd=repo)
    _run(["git", "commit", "-qm", f"release {version}"], cwd=repo)
    _run(["git", "tag", "-a", f"v{version}", "-m", f"v{version}"], cwd=repo)
    return _run(["git", "rev-parse", "HEAD"], cwd=repo)


def _build_and_extract(repo: Path, root: Path, version: str) -> tuple[Path, str]:
    output = root / f"output-{version}"
    archive, digest = builder.build_bundle(repo, output, f"v{version}")
    extracted = integrity.extract_verified_archive(
        archive,
        root / f"extract-{version}",
        digest,
    )
    manifest = integrity.load_and_verify_bundle(
        extracted, expected_repository=ident.identity().engine_repo
    )
    assert manifest["policy_version"] == version
    assert manifest["release_commit"] == _run(["git", "rev-parse", "HEAD"], cwd=repo)
    return extracted, digest


def _target_repo(root: Path, name: str, version: str) -> Path:
    repo = root / name
    repo.mkdir()
    (repo / ".project-policy.yml").write_text(
        f"policy_profile: flat\npolicy_version: {version}\n",
        encoding="utf-8",
    )
    return repo


def test_clean_tag_bundle_offline_install_upgrade_and_rollback(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    _run(["git", "clone", "-q", "--no-hardlinks", str(REPO), str(source)], cwd=tmp_path)
    _run(["git", "config", "user.email", "runtime@example.invalid"], cwd=source)
    _run(["git", "config", "user.name", "Runtime Bundle"], cwd=source)
    _run(
        [
            "git",
            "remote",
            "set-url",
            "origin",
            f"https://github.com/{ident.identity().engine_repo}.git",
        ],
        cwd=source,
    )

    first = "9.8.0"
    baseline = (source / "VERSION").read_text(encoding="utf-8").strip()
    _commit_release(source, baseline, first)
    first_bundle, first_digest = _build_and_extract(source, tmp_path, first)
    _repeat_archive, repeat_digest = builder.build_bundle(
        source,
        tmp_path / f"repeat-{first}",
        f"v{first}",
    )
    assert repeat_digest == first_digest

    runtime_root = tmp_path / "runtime"
    skill_target = tmp_path / "home" / ".agents" / "skills" / "preflight-ci"
    evil = tmp_path / "evil-pythonpath"
    evil.mkdir()
    (evil / "json.py").write_text(
        'raise RuntimeError("ambient PYTHONPATH loaded")\n',
        encoding="utf-8",
    )
    install_env = dict(os.environ)
    install_env["PYTHON_BIN"] = sys.executable
    install_env["PYTHONPATH"] = str(evil)
    install_output = _run(
        [
            str(first_bundle / "install.sh"),
            "--root",
            str(runtime_root),
            "--skill-target",
            str(skill_target),
        ],
        cwd=first_bundle,
        env=install_env,
    )
    assert install_output.splitlines()[-1] == f"INSTALLED {first}"

    second = "9.8.1"
    _commit_release(source, first, second)
    second_bundle, _second_digest = _build_and_extract(source, tmp_path, second)
    assert manager.install(second_bundle, runtime_root, skill_target) == second
    assert (runtime_root / "current").resolve().name == second

    first_target = _target_repo(tmp_path, "target-first", first)
    second_target = _target_repo(tmp_path, "target-second", second)
    missing_target = _target_repo(tmp_path, "target-missing", "9.8.2")
    assert manager.select_release(runtime_root, first_target)[0].name == first
    assert manager.select_release(runtime_root, second_target)[0].name == second
    with pytest.raises(manager.RuntimeBundleError, match="not installed"):
        manager.select_release(runtime_root, missing_target)

    lifecycle_env = dict(os.environ)
    lifecycle_env["PYTHON_BIN"] = sys.executable
    assert _run(
        [
            str(runtime_root / "bin" / "policy-runtime-bundle"),
            "rollback",
            "--skill-target",
            str(skill_target),
        ],
        cwd=runtime_root,
        env=lifecycle_env,
    ) == f"ROLLED BACK {first}"
    assert (runtime_root / "current").resolve().name == first
    active_verifier = (
        runtime_root
        / "releases"
        / first
        / "artifact"
        / "runtime"
        / "runtime_verifier.py"
    )
    with active_verifier.open("ab") as stream:
        stream.write(b"\ntampered active release\n")
    with pytest.raises(manager.RuntimeBundleError, match="checksum mismatch"):
        manager.select_release(runtime_root, first_target)
    assert manager.install(
        first_bundle,
        runtime_root,
        skill_target,
        force_reinstall=True,
    ) == first
    assert manager.select_release(runtime_root, first_target)[0].name == first

    yaml_init = next(
        (runtime_root / "releases" / first / "venv").glob(
            "lib/python*/site-packages/yaml/__init__.py"
        )
    )
    yaml_init.write_text("# tampered dependency\n", encoding="utf-8")
    with pytest.raises(manager.RuntimeBundleError, match="PyYAML"):
        manager.select_release(runtime_root, first_target)

    tampered = (
        runtime_root
        / "releases"
        / second
        / "artifact"
        / "runtime"
        / "runtime_verifier.py"
    )
    with tampered.open("ab") as stream:
        stream.write(b"\ntampered\n")
    with pytest.raises(manager.RuntimeBundleError, match="checksum mismatch"):
        manager.select_release(runtime_root, second_target)
    assert _run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=source,
    ) == ""
