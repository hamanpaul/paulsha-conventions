from __future__ import annotations

import base64
import hashlib
import json
import io
import os
import subprocess
import sys
import sysconfig
import tarfile
import zipfile
from pathlib import Path

import pytest

from policy_check.runtime_bundle import builder, cli, integrity, manager, verification


def _fake_bundle(
    root: Path,
    version: str = "1.0.13",
    *,
    repository: str = "hamanpaul/paulsha-conventions",
) -> Path:
    bundle = root / f"paulsha-conventions-v{version}"
    package_version = integrity.normalized_package_version(version)
    wheel = bundle / "wheels" / f"policy_check-{package_version}-py3-none-any.whl"
    wheel.parent.mkdir(parents=True)
    wheel.write_bytes(f"wheel-{version}".encode())
    skill = bundle / "skills" / "preflight-ci"
    (skill / "scripts").mkdir(parents=True)
    (skill / "SKILL.md").write_text("name: preflight-ci\n", encoding="utf-8")
    wrapper = skill / "scripts" / "preflight.sh"
    wrapper.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    wrapper.chmod(0o755)
    runtime = bundle / "runtime" / "runtime_manager.py"
    runtime.parent.mkdir()
    runtime.write_text("# stdlib runtime manager\n", encoding="utf-8")
    verifier = bundle / "runtime" / "runtime_verifier.py"
    verifier.write_text("# shared stdlib runtime verifier\n", encoding="utf-8")
    installer = bundle / "install.sh"
    installer.write_text(builder.INSTALLER, encoding="utf-8")
    installer.chmod(0o755)
    manifest = {
        "schema_version": 1,
        "policy_version": version,
        "skill_version": version,
        "package": {
            "name": "policy-check",
            "version": package_version,
            "requires_python": ">=3.11",
        },
        "repository": repository,
        "release_tag": f"v{version}",
        "release_commit": "a" * 40,
        "distribution": {
            "canonical_org": "hamanpaul",
            "engine_repo": "hamanpaul/paulsha-conventions",
            "remote_base": "https://github.com",
            "distribution_name": "paulsha-conventions",
            "provider": "github",
        },
        "wheels": [
            {
                "path": f"wheels/{wheel.name}",
                "sha256": integrity.sha256_file(wheel),
            }
        ],
        "skill": {
            "path": "skills/preflight-ci",
            "sha256": integrity.tree_sha256(skill),
        },
        "runtime": {
            "path": "runtime/runtime_manager.py",
            "sha256": integrity.sha256_file(runtime),
            "verifier_path": "runtime/runtime_verifier.py",
            "verifier_sha256": integrity.sha256_file(verifier),
        },
        "runtime_compatibility": {
            "implementation": sys.implementation.name,
            "python": f"{sys.version_info.major}.{sys.version_info.minor}",
            "abi": str(sysconfig.get_config_var("SOABI") or ""),
            "platform": sysconfig.get_platform(),
        },
        "prerequisites": [
            f"python=={sys.version_info.major}.{sys.version_info.minor}",
            f"abi=={sysconfig.get_config_var('SOABI') or ''}",
            f"platform=={sysconfig.get_platform()}",
            "python-venv+ensurepip",
            "git",
            "sha256sum",
            "universal-ctags",
        ],
    }
    (bundle / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    integrity.write_checksums(bundle)
    return bundle


def _install_fake_release(root: Path, version: str) -> Path:
    bundle = _fake_bundle(root / "sources", version)
    release = root / "runtime" / "releases" / version
    artifact = release / "artifact"
    artifact.parent.mkdir(parents=True)
    import shutil

    shutil.copytree(bundle, artifact)
    python = release / "venv" / (
        "Scripts/python.exe" if os.name == "nt" else "bin/python"
    )
    python.parent.mkdir(parents=True)
    python.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    python.chmod(0o755)
    pyvenv_cfg = release / "venv" / "pyvenv.cfg"
    pyvenv_cfg.write_text(
        "include-system-site-packages = false\n",
        encoding="utf-8",
    )
    (release / "VERIFIED").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "policy_version": version,
                "manifest_sha256": integrity.sha256_file(artifact / "manifest.json"),
                "python_sha256": integrity.sha256_file(python),
                "pyvenv_cfg_sha256": integrity.sha256_file(pyvenv_cfg),
            }
        ),
        encoding="utf-8",
    )
    return release


def _write_fake_venv(path: Path) -> None:
    python = path / (
        "Scripts/python.exe" if os.name == "nt" else "bin/python"
    )
    python.parent.mkdir(parents=True)
    python.write_text("# fake\n", encoding="utf-8")
    python.chmod(0o755)
    (path / "pyvenv.cfg").write_text(
        "include-system-site-packages = false\n",
        encoding="utf-8",
    )
    # Mirrors the layout `pip install` leaves behind for the real
    # `policy_check.data` package, so `manager._write_distribution_identity`
    # finds a target to write into during install() tests below.
    (manager._venv_site_packages(path) / "policy_check" / "data").mkdir(
        parents=True
    )


def test_verify_bundle_accepts_closed_file_set(tmp_path: Path) -> None:
    bundle = _fake_bundle(tmp_path)
    manifest = integrity.load_and_verify_bundle(
        bundle, expected_repository="hamanpaul/paulsha-conventions"
    )
    assert manifest["policy_version"] == "1.0.13"
    assert manager.verify_bundle(
        bundle, expected_repository="hamanpaul/paulsha-conventions"
    )["skill_version"] == "1.0.13"


def test_checksums_include_nested_file_named_sha256sums(tmp_path: Path) -> None:
    bundle = _fake_bundle(tmp_path)
    nested = bundle / "payload" / "SHA256SUMS"
    nested.parent.mkdir()
    nested.write_text("nested payload\n", encoding="utf-8")
    integrity.write_checksums(bundle)

    checksums = (bundle / "SHA256SUMS").read_text(encoding="utf-8")
    assert "payload/SHA256SUMS" in checksums
    assert integrity.load_and_verify_bundle(
        bundle, expected_repository="hamanpaul/paulsha-conventions"
    )["policy_version"] == "1.0.13"


def _vendor_bootstrap(bootstrap: Path, *, expected_repository: str) -> Path:
    """Build a standalone runtime_manager.py + runtime_verifier.py pair the
    way `builder.build_bundle` vendors them into a real bundle, so tests
    that execute the pair under `python3 -I`/`-P` (where policy_check is not
    importable) exercise the same build-time-baked repository constant that
    production bundles carry, instead of a raw, unvendored copy."""
    manager_source = Path(manager.__file__).resolve()
    verifier_source = manager_source.with_name("verification.py")
    runtime_manager = bootstrap / "runtime_manager.py"
    runtime_verifier = bootstrap / "runtime_verifier.py"
    builder._vendor_runtime_manager(
        manager_source,
        runtime_manager,
        expected_repository=expected_repository,
    )
    runtime_verifier.write_bytes(verifier_source.read_bytes())
    return runtime_manager


def test_vendored_manager_loads_the_shared_verifier_under_safe_path(
    tmp_path: Path,
) -> None:
    bundle = _fake_bundle(tmp_path / "bundle")
    bootstrap = tmp_path / "bootstrap"
    bootstrap.mkdir()
    runtime_manager = _vendor_bootstrap(
        bootstrap, expected_repository="hamanpaul/paulsha-conventions"
    )

    result = subprocess.run(
        [
            sys.executable,
            "-P",
            str(runtime_manager),
            "verify",
            "--bundle",
            str(bundle),
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "BUNDLE VERIFIED 1.0.13"


def test_vendored_manager_rejects_foreign_manifest_repository_when_identity_unavailable(
    tmp_path: Path,
) -> None:
    """A bundle whose manifest declares a repository other than the one
    baked into the vendored runtime manager at build time must still be
    rejected when `policy_check.identity` is unimportable (`-I`/`-P`), not
    silently accepted by comparing the manifest against itself."""
    bundle = _fake_bundle(
        tmp_path / "bundle",
        repository="evil-org/not-canonical-at-all",
    )
    bootstrap = tmp_path / "bootstrap"
    bootstrap.mkdir()
    runtime_manager = _vendor_bootstrap(
        bootstrap, expected_repository="hamanpaul/paulsha-conventions"
    )

    result = subprocess.run(
        [
            sys.executable,
            "-P",
            str(runtime_manager),
            "verify",
            "--bundle",
            str(bundle),
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "manifest repository is not canonical" in result.stderr


def test_expected_repository_fails_closed_without_identity_or_vendored_constant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Neither `policy_check.identity` nor a build-time vendored constant
    available must raise, never silently read the expected value back out
    of the bundle under verification."""
    monkeypatch.setattr(manager, "_identity", None)
    monkeypatch.setattr(manager, "_VENDORED_EXPECTED_REPOSITORY", None)
    with pytest.raises(
        manager.RuntimeBundleError, match="distribution identity is unavailable"
    ):
        manager._expected_repository()


def test_installer_reports_python_311_requirement_before_using_safe_path(
    tmp_path: Path,
) -> None:
    bundle = _fake_bundle(tmp_path / "bundle")
    incompatible = tmp_path / "python-old"
    incompatible.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
    incompatible.chmod(0o755)
    env = dict(os.environ)
    env["PYTHON_BIN"] = str(incompatible)

    result = subprocess.run(
        [str(bundle / "install.sh")],
        cwd=bundle,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "Python 3.11+" in result.stderr


def test_installer_reports_missing_venv_support_before_runtime_code(
    tmp_path: Path,
) -> None:
    bundle = _fake_bundle(tmp_path / "bundle")
    incompatible = tmp_path / "python-no-venv"
    incompatible.write_text(
        "#!/usr/bin/env bash\n"
        '[[ "${1:-}" == "-c" ]] && exit 0\n'
        "exit 1\n",
        encoding="utf-8",
    )
    incompatible.chmod(0o755)
    env = dict(os.environ)
    env["PYTHON_BIN"] = str(incompatible)

    result = subprocess.run(
        [str(bundle / "install.sh")],
        cwd=bundle,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "python3-venv" in result.stderr


def test_installer_reports_missing_manifest_command_before_runtime_code(
    tmp_path: Path,
) -> None:
    bundle = _fake_bundle(tmp_path / "bundle")
    command_dir = tmp_path / "commands"
    command_dir.mkdir()
    for command in ("bash", "dirname", "git", "sha256sum"):
        source = manager.shutil.which(command)
        assert source is not None
        (command_dir / command).symlink_to(source)
    env = dict(os.environ)
    env["PATH"] = str(command_dir)
    env["PYTHON_BIN"] = sys.executable

    result = subprocess.run(
        [str(bundle / "install.sh")],
        cwd=bundle,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "universal-ctags (ctags)" in result.stderr


def test_verify_bundle_accepts_fix_suffix_as_post_package_version(
    tmp_path: Path,
) -> None:
    bundle = _fake_bundle(tmp_path, "1.0.13-fix.2")
    manifest = integrity.load_and_verify_bundle(
        bundle, expected_repository="hamanpaul/paulsha-conventions"
    )
    assert manifest["policy_version"] == "1.0.13-fix.2"
    assert manifest["package"]["version"] == "1.0.13.post2"
    assert manager.verify_bundle(
        bundle, expected_repository="hamanpaul/paulsha-conventions"
    )["package"]["version"] == "1.0.13.post2"


@pytest.mark.parametrize(
    "relative",
    [
        "wheels/policy_check-1.0.13-py3-none-any.whl",
        "skills/preflight-ci/SKILL.md",
        "runtime/runtime_manager.py",
        "runtime/runtime_verifier.py",
        "manifest.json",
    ],
)
def test_verify_bundle_rejects_payload_tamper(tmp_path: Path, relative: str) -> None:
    bundle = _fake_bundle(tmp_path)
    with (bundle / relative).open("ab") as stream:
        stream.write(b"tampered")
    with pytest.raises(integrity.BundleError, match="checksum mismatch"):
        integrity.load_and_verify_bundle(
            bundle, expected_repository="hamanpaul/paulsha-conventions"
        )
    with pytest.raises(manager.RuntimeBundleError, match="checksum mismatch"):
        manager.verify_bundle(
            bundle, expected_repository="hamanpaul/paulsha-conventions"
        )


def test_verify_bundle_rejects_unlisted_file_and_symlink(tmp_path: Path) -> None:
    bundle = _fake_bundle(tmp_path)
    (bundle / "extra").write_text("unlisted\n", encoding="utf-8")
    with pytest.raises(integrity.BundleError, match="file set mismatch"):
        integrity.load_and_verify_bundle(
            bundle, expected_repository="hamanpaul/paulsha-conventions"
        )
    (bundle / "extra").unlink()
    (bundle / "escape").symlink_to("../outside")
    with pytest.raises(integrity.BundleError, match="symlink"):
        integrity.load_and_verify_bundle(
            bundle, expected_repository="hamanpaul/paulsha-conventions"
        )


def test_extract_archive_verifies_digest_members_and_payload(tmp_path: Path) -> None:
    bundle = _fake_bundle(tmp_path / "source")
    archive = tmp_path / "bundle.tar.gz"
    builder._deterministic_archive(bundle, archive, epoch=1_700_000_000)
    digest = integrity.sha256_file(archive)
    extracted = integrity.extract_verified_archive(
        archive,
        tmp_path / "output",
        digest,
    )
    assert extracted.name == "paulsha-conventions-v1.0.13"
    assert integrity.load_and_verify_bundle(
        extracted, expected_repository="hamanpaul/paulsha-conventions"
    )["policy_version"] == "1.0.13"
    with pytest.raises(integrity.BundleError, match="already exists"):
        integrity.extract_verified_archive(archive, tmp_path / "output", digest)


def test_deterministic_archive_normalizes_umask_sensitive_modes(
    tmp_path: Path,
) -> None:
    bundle = _fake_bundle(tmp_path / "source")
    archive_one = tmp_path / "one.tar.gz"
    archive_two = tmp_path / "two.tar.gz"
    for path in bundle.rglob("*"):
        if path.is_dir():
            path.chmod(0o700)
        elif path.name not in {"install.sh", "preflight.sh"}:
            path.chmod(0o600)
    builder._deterministic_archive(bundle, archive_one, epoch=1_700_000_000)
    for path in bundle.rglob("*"):
        if path.is_dir():
            path.chmod(0o755)
        elif path.name not in {"install.sh", "preflight.sh"}:
            path.chmod(0o644)
    builder._deterministic_archive(bundle, archive_two, epoch=1_700_000_000)
    assert integrity.sha256_file(archive_one) == integrity.sha256_file(archive_two)


@pytest.mark.parametrize("kind", ["duplicate", "traversal", "symlink"])
def test_extract_archive_rejects_unsafe_members(tmp_path: Path, kind: str) -> None:
    archive = tmp_path / f"{kind}.tar.gz"
    root = "paulsha-conventions-v1.0.13"
    with tarfile.open(archive, mode="w:gz") as bundle_tar:
        directory = tarfile.TarInfo(root)
        directory.type = tarfile.DIRTYPE
        bundle_tar.addfile(directory)
        if kind == "duplicate":
            for _ in range(2):
                member = tarfile.TarInfo(f"{root}/manifest.json")
                member.size = 2
                bundle_tar.addfile(member, io.BytesIO(b"{}"))
        elif kind == "traversal":
            member = tarfile.TarInfo(f"{root}/../escape")
            member.size = 1
            bundle_tar.addfile(member, io.BytesIO(b"x"))
        else:
            member = tarfile.TarInfo(f"{root}/escape")
            member.type = tarfile.SYMTYPE
            member.linkname = "../../outside"
            bundle_tar.addfile(member)
    with pytest.raises(integrity.BundleError):
        integrity.extract_verified_archive(
            archive,
            tmp_path / "output",
            integrity.sha256_file(archive),
        )


def test_safe_relative_path_rejects_dot_segments() -> None:
    for value in ("../payload", "a/../payload", "a/./payload", "/payload", "a//b"):
        with pytest.raises(integrity.BundleError):
            integrity.safe_relative_path(value, field="payload")


def test_installer_checksums_before_runtime_code() -> None:
    checksum = builder.INSTALLER.index("sha256sum --check")
    runtime = builder.INSTALLER.index("runtime_manager.py")
    assert checksum < runtime
    assert "--no-index" in Path(manager.__file__).read_text(encoding="utf-8")


def test_runtime_command_failure_includes_bounded_diagnostic(tmp_path: Path) -> None:
    with pytest.raises(manager.RuntimeBundleError, match="useful failure"):
        manager._run(
            [
                sys.executable,
                "-c",
                "import sys; print('useful failure', file=sys.stderr); raise SystemExit(7)",
            ],
            cwd=tmp_path,
        )


def test_runtime_command_failure_preserves_bounded_multiline_diagnostic(
    tmp_path: Path,
) -> None:
    with pytest.raises(manager.RuntimeBundleError) as failure:
        manager._run(
            [
                sys.executable,
                "-c",
                "import sys; "
                "print('policy: FAIL (universal-ctags unavailable)', file=sys.stderr); "
                "print('PREFLIGHT FAIL', file=sys.stderr); "
                "raise SystemExit(1)",
            ],
            cwd=tmp_path,
        )
    assert "universal-ctags unavailable" in str(failure.value)
    assert "PREFLIGHT FAIL" in str(failure.value)


def test_default_root_prefers_explicit_runtime_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = tmp_path / "configured"
    monkeypatch.setenv("PSC_CONVENTIONS_ROOT", str(configured))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert manager._default_root() == configured


def test_attest_clean_annotated_tag_and_rejects_dirty(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(
        [
            "git",
            "remote",
            "add",
            "origin",
            "https://github.com/hamanpaul/paulsha-conventions.git",
        ],
        cwd=repo,
        check=True,
    )
    (repo / "VERSION").write_text("1.0.13\n", encoding="utf-8")
    subprocess.run(["git", "add", "VERSION"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "release"], cwd=repo, check=True)
    subprocess.run(
        ["git", "tag", "-a", "v1.0.13", "-m", "v1.0.13"],
        cwd=repo,
        check=True,
    )
    version, commit, epoch = builder.attest_clean_tag(repo, "v1.0.13")
    assert version == "1.0.13"
    assert len(commit) == 40
    assert epoch > 0
    snapshot = builder._tag_snapshot(repo, "v1.0.13", tmp_path / "snapshot")
    assert (snapshot / "VERSION").read_text(encoding="utf-8") == "1.0.13\n"
    assert (
        subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=repo,
            text=True,
        )
        == ""
    )
    (repo / "dirty").write_text("x", encoding="utf-8")
    with pytest.raises(integrity.BundleError, match="not clean"):
        builder.attest_clean_tag(repo, "v1.0.13")


def test_prepare_package_version_normalizes_fix_suffix_in_snapshot(
    tmp_path: Path,
) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    pyproject = snapshot / "pyproject.toml"
    pyproject.write_text(
        '[build-system]\nrequires = ["setuptools"]\n\n'
        '[project]\nname = "policy-check"\nversion = "1.0.13-fix.2"\n',
        encoding="utf-8",
    )

    builder._prepare_package_version(snapshot, "1.0.13-fix.2")

    assert 'version = "1.0.13.post2"' in pyproject.read_text(encoding="utf-8")


def test_prepare_package_version_rejects_mismatched_snapshot(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / "pyproject.toml").write_text(
        '[project]\nversion = "1.0.13"\n',
        encoding="utf-8",
    )

    with pytest.raises(integrity.BundleError, match="does not match"):
        builder._prepare_package_version(snapshot, "1.0.13-fix.2")


def test_runtime_constraints_lock_every_direct_project_dependency(
    tmp_path: Path,
) -> None:
    repo = Path(__file__).resolve().parents[1]
    builder._validate_runtime_constraints(repo)

    snapshot = tmp_path / "snapshot"
    constraints = snapshot / "policy_check" / "runtime_bundle" / "constraints.txt"
    constraints.parent.mkdir(parents=True)
    constraints.write_text("PyYAML==6.0.3\n", encoding="utf-8")
    (snapshot / "pyproject.toml").write_text(
        '[project]\ndependencies = ["PyYAML>=6.0", "example-dep>=1"]\n',
        encoding="utf-8",
    )
    with pytest.raises(integrity.BundleError, match="example-dep"):
        builder._validate_runtime_constraints(snapshot)


def test_resolved_dependency_closure_requires_exact_constraints(
    tmp_path: Path,
) -> None:
    wheels = tmp_path / "wheels"
    wheels.mkdir()

    def wheel(name: str, version: str) -> None:
        path = wheels / f"{name}-{version}-py3-none-any.whl"
        dist_info = f"{name}-{version}.dist-info"
        with zipfile.ZipFile(path, mode="w") as archive:
            archive.writestr(
                f"{dist_info}/METADATA",
                f"Name: {name}\nVersion: {version}\n",
            )

    wheel("policy_check", "1.0.13")
    wheel("PyYAML", "6.0.3")
    wheel("transitive_dep", "2.4.0")

    with pytest.raises(integrity.BundleError, match="transitive-dep"):
        builder._validate_resolved_wheel_constraints(
            wheels,
            {"pyyaml": "6.0.3"},
        )
    builder._validate_resolved_wheel_constraints(
        wheels,
        {"pyyaml": "6.0.3", "transitive-dep": "2.4.0"},
    )


def test_bundle_output_must_be_outside_source(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    with pytest.raises(integrity.BundleError, match="outside"):
        builder._prepare_output_directory(source, source / "dist")
    outside = builder._prepare_output_directory(source, tmp_path / "dist")
    assert outside == (tmp_path / "dist").resolve()


def test_selector_chooses_exact_version_and_never_current(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root = tmp_path / "runtime"
    first = _install_fake_release(tmp_path, "1.0.13")
    second = _install_fake_release(tmp_path, "1.0.14")
    (runtime_root / "current").symlink_to(second)
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".project-policy.yml").write_text(
        "policy_profile: flat\npolicy_version: 1.0.13\n",
        encoding="utf-8",
    )

    events: list[str] = []

    def fake_run(argv, **_kwargs):
        assert events == ["attested"]
        python = Path(argv[0])
        return python.parents[2].name

    monkeypatch.setattr(manager, "_run", fake_run)
    monkeypatch.setattr(
        manager,
        "_attest_installed_release",
        lambda *_a: events.append("attested"),
    )
    selected, manifest = manager.select_release(runtime_root, repo)
    assert selected == first
    assert manifest["policy_version"] == "1.0.13"


def test_selector_missing_version_and_alias_conflict_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root = tmp_path / "runtime"
    _install_fake_release(tmp_path, "1.0.13")
    repo = tmp_path / "repo"
    repo.mkdir()
    canonical = repo / ".project-policy.yml"
    canonical.write_text(
        "policy_profile: flat\npolicy_version: 1.0.14\n",
        encoding="utf-8",
    )
    with pytest.raises(manager.RuntimeBundleError, match="not installed"):
        manager.select_release(runtime_root, repo)
    (repo / ".paul-project.yml").write_text(
        "policy_profile: flat\npolicy_version: 1.0.13\n",
        encoding="utf-8",
    )
    with pytest.raises(manager.RuntimeBundleError, match="disagree"):
        manager.select_release(runtime_root, repo)


def test_selector_accepts_inline_policy_version_comment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root = tmp_path / "runtime"
    expected = _install_fake_release(tmp_path, "1.0.13")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".project-policy.yml").write_text(
        "policy_profile: flat\npolicy_version: 1.0.13  # managed\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(manager, "_run", lambda *_a, **_kw: "1.0.13")
    monkeypatch.setattr(manager, "_attest_installed_release", lambda *_a: None)
    selected, _manifest = manager.select_release(runtime_root, repo)
    assert selected == expected


@pytest.mark.parametrize(
    "relative",
    [
        Path("venv") / ("Scripts/python.exe" if os.name == "nt" else "bin/python"),
        Path("venv") / "pyvenv.cfg",
    ],
)
def test_verified_release_rejects_venv_runtime_identity_tamper(
    tmp_path: Path,
    relative: Path,
) -> None:
    release = _install_fake_release(tmp_path, "1.0.13")
    with (release / relative).open("ab") as stream:
        stream.write(b"tampered\n")

    with pytest.raises(manager.RuntimeBundleError, match="marker does not match"):
        manager._verified_release(tmp_path / "runtime", "1.0.13")


def test_activate_rejects_release_that_fails_installed_attestation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_release(tmp_path, "1.0.13")
    runtime_root = tmp_path / "runtime"
    skill_target = tmp_path / "skills" / "preflight-ci"

    def reject_tampered_release(_release: Path) -> None:
        raise manager.RuntimeBundleError("installed wheel was modified")

    monkeypatch.setattr(
        manager,
        "_attest_installed_release",
        reject_tampered_release,
    )
    with pytest.raises(manager.RuntimeBundleError, match="installed wheel"):
        manager.activate(runtime_root, skill_target, "1.0.13")

    assert not (runtime_root / "current").exists()
    assert not skill_target.exists()
    assert not (runtime_root / "state.json").exists()


def test_install_rejects_incompatible_runtime_before_staging(tmp_path: Path) -> None:
    bundle = _fake_bundle(tmp_path / "source")
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["runtime_compatibility"]["python"] = "99.99"
    manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    integrity.write_checksums(bundle)
    runtime_root = tmp_path / "runtime"
    with pytest.raises(manager.RuntimeBundleError, match="incompatible"):
        manager.install(
            bundle,
            runtime_root,
            tmp_path / "skills" / "preflight-ci",
        )
    assert not runtime_root.exists()


def test_install_rejects_missing_venv_support_before_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _fake_bundle(tmp_path / "source")
    runtime_root = tmp_path / "runtime"

    def fail_ensurepip(*_args, **_kwargs):
        raise manager.RuntimeBundleError("ensurepip missing")

    monkeypatch.setattr(manager, "_run", fail_ensurepip)
    with pytest.raises(manager.RuntimeBundleError, match="python3-venv"):
        manager.install(
            bundle,
            runtime_root,
            tmp_path / "skills" / "preflight-ci",
        )
    assert not (runtime_root / "releases").exists()


def test_install_rejects_missing_manifest_command_before_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _fake_bundle(tmp_path / "source")
    runtime_root = tmp_path / "runtime"
    real_which = manager.shutil.which

    monkeypatch.setattr(manager, "_require_venv_support", lambda *_a: None)
    monkeypatch.setattr(
        manager.shutil,
        "which",
        lambda command: None if command == "ctags" else real_which(command),
    )
    with pytest.raises(
        manager.RuntimeBundleError,
        match=r"universal-ctags \(ctags\)",
    ):
        manager.install(
            bundle,
            runtime_root,
            tmp_path / "skills" / "preflight-ci",
        )
    assert not (runtime_root / "releases").exists()


def test_install_wraps_venv_creation_failure_and_removes_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _fake_bundle(tmp_path / "source")
    runtime_root = tmp_path / "runtime"

    class BrokenEnvBuilder:
        def __init__(self, **_kwargs):
            pass

        def create(self, _path):
            raise subprocess.CalledProcessError(1, ["python", "-m", "venv"])

    monkeypatch.setattr(manager.venv, "EnvBuilder", BrokenEnvBuilder)
    monkeypatch.setattr(manager, "_run", lambda *_a, **_kw: "")
    with pytest.raises(manager.RuntimeBundleError, match="python3-venv"):
        manager.install(
            bundle,
            runtime_root,
            tmp_path / "skills" / "preflight-ci",
        )
    assert not list((runtime_root / "releases").glob(".staging-*"))
    assert not (runtime_root / "releases" / "1.0.13").exists()


def test_install_upgrade_rollback_and_uninstall_are_scoped(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _fake_bundle(tmp_path / "one", "1.0.13")
    second = _fake_bundle(tmp_path / "two", "1.0.14")
    runtime_root = tmp_path / "runtime"
    skill_target = tmp_path / "home" / ".agents" / "skills" / "preflight-ci"

    class FakeEnvBuilder:
        def __init__(self, **_kwargs):
            pass

        def create(self, path):
            _write_fake_venv(Path(path))

    monkeypatch.setattr(manager.venv, "EnvBuilder", FakeEnvBuilder)
    monkeypatch.setattr(manager, "_run", lambda *_a, **_kw: "")
    monkeypatch.setattr(manager, "_smoke", lambda *_a, **_kw: None)
    monkeypatch.setattr(
        manager,
        "_attest_installed_release",
        lambda *_a, **_kw: None,
    )

    assert manager.install(first, runtime_root, skill_target) == "1.0.13"
    assert manager.install(second, runtime_root, skill_target) == "1.0.14"
    assert (runtime_root / "current").resolve().name == "1.0.14"
    assert skill_target.is_symlink()
    assert manager.rollback(runtime_root, skill_target, None) == "1.0.13"
    assert (runtime_root / "current").resolve().name == "1.0.13"
    manager.uninstall(runtime_root, "1.0.14")
    assert not (runtime_root / "releases" / "1.0.14").exists()


def test_install_writes_distribution_identity_into_the_installed_venv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression for a plan-mandated defect found in review: the identity
    write must resolve the venv `install()` itself just created (`staging /
    "venv"`, which becomes `releases/<version>/venv`) rather than a bare
    `python3` / ambient `importlib.util.find_spec("policy_check.data")`
    lookup on the invoking interpreter. On a real host — and in this very
    test process, since `policy_check` is importable here as an editable
    checkout — an ambient lookup would resolve to this repo's own tracked
    `policy_check/data/distribution.yml`, not the release being installed.
    """
    bundle = _fake_bundle(tmp_path / "source")
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    runtime_root = tmp_path / "runtime"
    skill_target = tmp_path / "skills" / "preflight-ci"

    class FakeEnvBuilder:
        def __init__(self, **_kwargs):
            pass

        def create(self, path):
            _write_fake_venv(Path(path))

    monkeypatch.setattr(manager.venv, "EnvBuilder", FakeEnvBuilder)
    monkeypatch.setattr(manager, "_run", lambda *_a, **_kw: "")
    monkeypatch.setattr(manager, "_smoke", lambda *_a, **_kw: None)
    monkeypatch.setattr(
        manager,
        "_attest_installed_release",
        lambda *_a, **_kw: None,
    )

    assert manager.install(bundle, runtime_root, skill_target) == "1.0.13"

    release_venv = runtime_root / "releases" / "1.0.13" / "venv"
    written = (
        manager._venv_site_packages(release_venv)
        / "policy_check"
        / "data"
        / "distribution.yml"
    )
    assert written.is_file()
    text = written.read_text(encoding="utf-8")
    for key, value in manifest["distribution"].items():
        assert f"{key}: {value}" in text

    import policy_check.data as _ambient_data

    ambient = Path(_ambient_data.__file__).resolve().parent / "distribution.yml"
    assert written.resolve() != ambient


def test_install_fails_closed_when_manifest_lacks_distribution_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _fake_bundle(tmp_path / "source")
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    del manifest["distribution"]
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    integrity.write_checksums(bundle)
    runtime_root = tmp_path / "runtime"
    skill_target = tmp_path / "skills" / "preflight-ci"

    class FakeEnvBuilder:
        def __init__(self, **_kwargs):
            pass

        def create(self, path):
            _write_fake_venv(Path(path))

    monkeypatch.setattr(manager.venv, "EnvBuilder", FakeEnvBuilder)
    monkeypatch.setattr(manager, "_run", lambda *_a, **_kw: "")
    monkeypatch.setattr(manager, "_smoke", lambda *_a, **_kw: None)
    monkeypatch.setattr(
        manager,
        "_attest_installed_release",
        lambda *_a, **_kw: None,
    )

    with pytest.raises(manager.RuntimeBundleError, match="distribution identity"):
        manager.install(bundle, runtime_root, skill_target)
    assert not (runtime_root / "releases" / "1.0.13").exists()
    assert not list((runtime_root / "releases").glob(".staging-*"))


def test_force_reinstall_recovers_tampered_active_release(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _fake_bundle(tmp_path / "source")
    runtime_root = tmp_path / "runtime"
    skill_target = tmp_path / "skills" / "preflight-ci"

    class FakeEnvBuilder:
        def __init__(self, **_kwargs):
            pass

        def create(self, path):
            _write_fake_venv(Path(path))

    monkeypatch.setattr(manager.venv, "EnvBuilder", FakeEnvBuilder)
    monkeypatch.setattr(manager, "_run", lambda *_a, **_kw: "")
    monkeypatch.setattr(manager, "_smoke", lambda *_a, **_kw: None)
    monkeypatch.setattr(
        manager,
        "_attest_installed_release",
        lambda *_a, **_kw: None,
    )

    assert manager.install(bundle, runtime_root, skill_target) == "1.0.13"
    active_manifest = (
        runtime_root / "releases" / "1.0.13" / "artifact" / "manifest.json"
    )
    active_manifest.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(manager.RuntimeBundleError):
        manager._verified_release(runtime_root, "1.0.13")

    assert manager.install(
        bundle,
        runtime_root,
        skill_target,
        force_reinstall=True,
    ) == "1.0.13"
    assert manager._verified_release(runtime_root, "1.0.13").name == "1.0.13"
    state = json.loads((runtime_root / "state.json").read_text(encoding="utf-8"))
    assert state["current"] == "1.0.13"
    assert state["previous"] is None


def test_force_reinstall_cleanup_failure_is_warning_after_successful_switch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = _fake_bundle(tmp_path / "source")
    runtime_root = tmp_path / "runtime"
    skill_target = tmp_path / "skills" / "preflight-ci"

    class FakeEnvBuilder:
        def __init__(self, **_kwargs):
            pass

        def create(self, path):
            _write_fake_venv(Path(path))

    monkeypatch.setattr(manager.venv, "EnvBuilder", FakeEnvBuilder)
    monkeypatch.setattr(manager, "_run", lambda *_a, **_kw: "")
    monkeypatch.setattr(manager, "_smoke", lambda *_a, **_kw: None)
    monkeypatch.setattr(
        manager,
        "_attest_installed_release",
        lambda *_a, **_kw: None,
    )
    assert manager.install(bundle, runtime_root, skill_target) == "1.0.13"

    real_rmtree = manager.shutil.rmtree

    def fail_old_release_cleanup(path, *args, **kwargs):
        if Path(path).name.startswith(".replaced-"):
            raise OSError("simulated cleanup failure")
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(manager.shutil, "rmtree", fail_old_release_cleanup)
    assert manager.install(
        bundle,
        runtime_root,
        skill_target,
        force_reinstall=True,
    ) == "1.0.13"
    assert manager._verified_release(runtime_root, "1.0.13").name == "1.0.13"
    assert "cleanup failed" in capsys.readouterr().err


def test_rollback_repairs_already_active_target_without_corrupting_previous(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _install_fake_release(tmp_path, "1.0.13")
    second = _install_fake_release(tmp_path, "1.0.14")
    runtime_root = tmp_path / "runtime"
    skill_target = tmp_path / "skills" / "preflight-ci"
    (runtime_root / "current").symlink_to(second)
    (runtime_root / "state.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "current": "1.0.14",
                "previous": "1.0.13",
                "installed": ["1.0.13", "1.0.14"],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(manager, "_install_launcher", lambda *_a, **_kw: None)
    monkeypatch.setattr(
        manager,
        "_attest_installed_release",
        lambda *_a, **_kw: None,
    )

    assert manager.rollback(runtime_root, skill_target, "1.0.14") == "1.0.14"
    state = json.loads((runtime_root / "state.json").read_text(encoding="utf-8"))
    assert state["previous"] == first.name
    assert skill_target.resolve() == (
        second / "artifact" / "skills" / "preflight-ci"
    ).resolve()


def test_activate_repairs_managed_links_without_rewriting_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _install_fake_release(tmp_path, "1.0.13")
    second = _install_fake_release(tmp_path, "1.0.14")
    runtime_root = tmp_path / "runtime"
    skill_target = tmp_path / "skills" / "preflight-ci"
    (runtime_root / "current").symlink_to(first)
    skill_target.parent.mkdir(parents=True)
    skill_target.symlink_to(first / "artifact" / "skills" / "preflight-ci")
    state_path = runtime_root / "state.json"
    original_state = {
        "schema_version": 1,
        "current": "1.0.14",
        "previous": "1.0.13",
        "installed": ["1.0.13", "1.0.14"],
    }
    state_path.write_text(json.dumps(original_state), encoding="utf-8")
    monkeypatch.setattr(
        manager,
        "_attest_installed_release",
        lambda *_a, **_kw: None,
    )

    manager.activate(runtime_root, skill_target, "1.0.14")

    assert (runtime_root / "current").resolve() == second.resolve()
    assert skill_target.resolve() == (
        second / "artifact" / "skills" / "preflight-ci"
    ).resolve()
    assert json.loads(state_path.read_text(encoding="utf-8")) == original_state
    assert (runtime_root / "bin" / "policy-preflight").is_file()
    assert (runtime_root / "bin" / "policy-runtime-bundle").is_file()


def test_failed_activation_restores_state_links_launchers_and_release(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _fake_bundle(tmp_path / "one", "1.0.13")
    second = _fake_bundle(tmp_path / "two", "1.0.14")
    runtime_root = tmp_path / "runtime"
    skill_target = tmp_path / "skills" / "preflight-ci"

    class FakeEnvBuilder:
        def __init__(self, **_kwargs):
            pass

        def create(self, path):
            _write_fake_venv(Path(path))

    monkeypatch.setattr(manager.venv, "EnvBuilder", FakeEnvBuilder)
    monkeypatch.setattr(manager, "_run", lambda *_a, **_kw: "")
    monkeypatch.setattr(manager, "_smoke", lambda *_a, **_kw: None)
    monkeypatch.setattr(
        manager,
        "_attest_installed_release",
        lambda *_a, **_kw: None,
    )
    assert manager.install(first, runtime_root, skill_target) == "1.0.13"
    before_state = (runtime_root / "state.json").read_bytes()
    before_current = os.readlink(runtime_root / "current")
    before_skill = os.readlink(skill_target)
    before_preflight = (runtime_root / "bin" / "policy-preflight").read_bytes()
    before_lifecycle = (
        runtime_root / "bin" / "policy-runtime-bundle"
    ).read_bytes()

    real_atomic_symlink = manager._atomic_symlink

    def fail_new_skill_link(target: Path, link: Path) -> None:
        if link == skill_target and "1.0.14" in str(target):
            raise OSError("simulated skill activation failure")
        real_atomic_symlink(target, link)

    monkeypatch.setattr(manager, "_atomic_symlink", fail_new_skill_link)
    with pytest.raises(OSError, match="simulated skill activation"):
        manager.install(second, runtime_root, skill_target)

    assert (runtime_root / "state.json").read_bytes() == before_state
    assert os.readlink(runtime_root / "current") == before_current
    assert os.readlink(skill_target) == before_skill
    assert (runtime_root / "bin" / "policy-preflight").read_bytes() == before_preflight
    assert (
        runtime_root / "bin" / "policy-runtime-bundle"
    ).read_bytes() == before_lifecycle
    assert not (runtime_root / "releases" / "1.0.14").exists()


def test_failed_force_reinstall_restores_displaced_release(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _fake_bundle(tmp_path / "source", "1.0.13")
    runtime_root = tmp_path / "runtime"
    skill_target = tmp_path / "skills" / "preflight-ci"

    class FakeEnvBuilder:
        def __init__(self, **_kwargs):
            pass

        def create(self, path):
            _write_fake_venv(Path(path))

    monkeypatch.setattr(manager.venv, "EnvBuilder", FakeEnvBuilder)
    monkeypatch.setattr(manager, "_run", lambda *_a, **_kw: "")
    monkeypatch.setattr(manager, "_smoke", lambda *_a, **_kw: None)
    monkeypatch.setattr(
        manager,
        "_attest_installed_release",
        lambda *_a, **_kw: None,
    )
    assert manager.install(bundle, runtime_root, skill_target) == "1.0.13"
    old_release = runtime_root / "releases" / "1.0.13"
    sentinel = old_release / "old-release-sentinel"
    sentinel.write_text("preserve old release\n", encoding="utf-8")
    before_state = (runtime_root / "state.json").read_bytes()

    real_atomic_symlink = manager._atomic_symlink

    def fail_skill_link(target: Path, link: Path) -> None:
        if link == skill_target:
            raise OSError("simulated force activation failure")
        real_atomic_symlink(target, link)

    monkeypatch.setattr(manager, "_atomic_symlink", fail_skill_link)
    with pytest.raises(OSError, match="simulated force activation"):
        manager.install(
            bundle,
            runtime_root,
            skill_target,
            force_reinstall=True,
        )

    assert sentinel.read_text(encoding="utf-8") == "preserve old release\n"
    assert (runtime_root / "state.json").read_bytes() == before_state
    assert (runtime_root / "current").resolve() == old_release.resolve()
    assert not list((runtime_root / "releases").glob(".failed-*"))
    assert not list((runtime_root / "releases").glob(".replaced-*"))


def test_public_cli_forwards_force_reinstall(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: list[str] = []

    def fake_manager_main(argv):
        received.extend(argv)
        return 0

    monkeypatch.setattr(cli, "manager_main", fake_manager_main)
    assert cli.main(
        [
            "install",
            "--bundle",
            str(tmp_path / "bundle"),
            "--force-reinstall",
        ]
    ) == 0
    assert received == [
        "install",
        "--bundle",
        str(tmp_path / "bundle"),
        "--force-reinstall",
    ]


def test_public_cli_forwards_activate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: list[str] = []
    monkeypatch.setattr(
        cli,
        "manager_main",
        lambda argv: received.extend(argv) or 0,
    )

    assert cli.main(
        ["activate", "--root", str(tmp_path), "--version", "1.0.13"]
    ) == 0
    assert received == [
        "activate",
        "--root",
        str(tmp_path),
        "--version",
        "1.0.13",
    ]


def test_install_records_state_before_switching_current(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _fake_bundle(tmp_path / "source")
    runtime_root = tmp_path / "runtime"
    skill_target = tmp_path / "skills" / "preflight-ci"
    events: list[str] = []

    class FakeEnvBuilder:
        def __init__(self, **_kwargs):
            pass

        def create(self, path):
            _write_fake_venv(Path(path))

    real_write = manager._write_json_atomic
    real_link = manager._atomic_symlink

    def record_write(path, value):
        if Path(path).name == "state.json":
            events.append("state")
        return real_write(path, value)

    def record_link(target, link):
        if Path(link).name == "current":
            events.append("current")
        return real_link(target, link)

    monkeypatch.setattr(manager.venv, "EnvBuilder", FakeEnvBuilder)
    monkeypatch.setattr(manager, "_run", lambda *_a, **_kw: "")
    monkeypatch.setattr(manager, "_smoke", lambda *_a, **_kw: None)
    monkeypatch.setattr(
        manager,
        "_attest_installed_release",
        lambda *_a, **_kw: None,
    )
    monkeypatch.setattr(manager, "_write_json_atomic", record_write)
    monkeypatch.setattr(manager, "_atomic_symlink", record_link)
    manager.install(bundle, runtime_root, skill_target)
    assert events.index("state") < events.index("current")


def test_install_preserves_unmanaged_skill_target(tmp_path: Path) -> None:
    bundle = _fake_bundle(tmp_path / "source")
    runtime_root = tmp_path / "runtime"
    skill_target = tmp_path / "skills" / "preflight-ci"
    skill_target.mkdir(parents=True)
    sentinel = skill_target / "sentinel"
    sentinel.write_text("keep\n", encoding="utf-8")
    with pytest.raises(manager.RuntimeBundleError, match="unmanaged"):
        manager.install(bundle, runtime_root, skill_target)
    assert sentinel.read_text(encoding="utf-8") == "keep\n"
    assert not (runtime_root / "releases" / "1.0.13").exists()


def test_uninstall_rejects_non_object_state(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    (runtime_root / "state.json").write_text("[]\n", encoding="utf-8")
    with pytest.raises(manager.RuntimeBundleError, match="JSON object"):
        manager.uninstall(runtime_root, "1.0.13")


def test_install_rejects_corrupt_state_before_creating_release(
    tmp_path: Path,
) -> None:
    bundle = _fake_bundle(tmp_path / "source")
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    (runtime_root / "state.json").write_text("[]\n", encoding="utf-8")
    with pytest.raises(manager.RuntimeBundleError, match="JSON object"):
        manager.install(
            bundle,
            runtime_root,
            tmp_path / "skills" / "preflight-ci",
        )
    assert not (runtime_root / "releases").exists()


def test_launcher_derives_root_and_rejects_forwarded_repo(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    scope = tmp_path / 'scope-$("unsafe")'
    release = _install_fake_release(scope, "1.0.13")
    runtime_root = scope / "runtime"
    (runtime_root / "current").symlink_to(release)
    manager._install_launcher(runtime_root, release)
    text = (runtime_root / "bin" / "policy-preflight").read_text(encoding="utf-8")
    assert str(runtime_root) not in text
    assert 'dirname "${BASH_SOURCE[0]}"' in text
    assert 'TARGET_REPO="$PWD"' in text
    assert "PSC_CONVENTIONS_ROOT" not in text
    assert 'exec "$PYTHON_BIN" -I -B "$MANAGER"' in text
    lifecycle = (
        runtime_root / "bin" / "policy-runtime-bundle"
    ).read_text(encoding="utf-8")
    assert "install|activate|rollback|uninstall" in lifecycle
    assert 'exec "$PYTHON_BIN" -I -B "$MANAGER"' in lifecycle
    assert manager.main(
        [
            "exec",
            "--root",
            str(runtime_root),
            "--repo",
            str(tmp_path),
            "--",
            "--repo",
            str(tmp_path / "other"),
        ]
    ) == 1
    assert "conflicts" in capsys.readouterr().err


def test_launcher_refuses_tampered_active_manager_before_execution(
    tmp_path: Path,
) -> None:
    release = _install_fake_release(tmp_path, "1.0.13")
    runtime_root = tmp_path / "runtime"
    (runtime_root / "current").symlink_to(release)
    manager._install_launcher(runtime_root, release)
    lifecycle = runtime_root / "bin" / "policy-runtime-bundle"
    env = dict(os.environ)
    env["PYTHON_BIN"] = sys.executable

    baseline = subprocess.run(
        [str(lifecycle), "activate", "--version", "1.0.13"],
        cwd=runtime_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert baseline.returncode == 0, baseline.stderr

    active_manager = (
        release / "artifact" / "runtime" / "runtime_manager.py"
    )
    active_manager.write_text(
        "raise RuntimeError('executed tampered manager')\n",
        encoding="utf-8",
    )
    tampered = subprocess.run(
        [str(lifecycle), "activate", "--version", "1.0.13"],
        cwd=runtime_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert tampered.returncode == 2
    assert "manager checksum mismatch" in tampered.stderr
    assert "executed tampered manager" not in tampered.stderr


@pytest.mark.parametrize(
    "option",
    ["--repo", "--installed-manifest", "--engine-source"],
)
def test_exec_rejects_forwarded_engine_authority_options(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    option: str,
) -> None:
    assert manager.main(
        [
            "exec",
            "--root",
            str(tmp_path / "runtime"),
            "--repo",
            str(tmp_path),
            "--",
            option,
            str(tmp_path / "override"),
        ]
    ) == 1
    assert "authority option" in capsys.readouterr().err


def test_smoke_repo_ignores_ambient_git_signing_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    global_config = tmp_path / "gitconfig"
    global_config.write_text(
        "[commit]\n\tgpgsign = true\n"
        "[gpg]\n\tprogram = /nonexistent/gpg-binary\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))
    fixture_root = tmp_path / "fixture-root"
    fixture_root.mkdir()
    repo, _body = manager._make_smoke_repo(fixture_root, "1.0.13")
    assert (
        subprocess.check_output(
            ["git", "log", "-1", "--format=%s"],
            cwd=repo,
            text=True,
        ).strip()
        == "chore: runtime smoke baseline"
    )


def test_uninstall_removes_tampered_but_state_owned_inactive_release(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    release = runtime_root / "releases" / "1.0.13"
    release.mkdir(parents=True)
    (release / "tampered").write_text("broken\n", encoding="utf-8")
    (runtime_root / "state.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "current": "1.0.14",
                "previous": "1.0.13",
                "installed": ["1.0.13", "1.0.14"],
            }
        ),
        encoding="utf-8",
    )
    manager.uninstall(runtime_root, "1.0.13")
    assert not release.exists()


def test_verification_module_stays_stdlib_only():
    """verification.py 由 vendored bootstrap manager 共用，不得引入第三方或套件內依賴。"""
    from pathlib import Path

    source = Path("policy_check/runtime_bundle/verification.py").read_text(encoding="utf-8")
    assert "import yaml" not in source
    assert "policy_check.identity" not in source


def test_manifest_repository_is_checked_against_argument():
    from policy_check.runtime_bundle import verification

    manifest = {
        "schema_version": verification.SCHEMA_VERSION,
        "policy_version": "1.0.15",
        "skill_version": "1.0.15",
        "repository": "hamanpaul/arc-conventions",
        "release_tag": "v1.0.15",
        "release_commit": "0" * 40,
        "package": {
            "name": "policy-check",
            "version": "1.0.15",
            "requires_python": ">=3.11",
        },
        "wheels": [{"path": "wheels/policy_check-1.0.15-py3-none-any.whl", "sha256": "a" * 64}],
        "skill": {"path": "skills/preflight-ci", "sha256": "a" * 64},
        "runtime": {
            "path": "runtime/runtime_manager.py",
            "sha256": "a" * 64,
            "verifier_path": "runtime/runtime_verifier.py",
            "verifier_sha256": "a" * 64,
        },
        "runtime_compatibility": {
            "implementation": "cpython",
            "python": "3.11",
            "abi": "cp311",
            "platform": "linux",
        },
        "prerequisites": ["git"],
    }
    with pytest.raises(verification.BundleError):
        verification._require_manifest_shape(manifest, "hamanpaul/paulsha-conventions")
    verification._require_manifest_shape(manifest, "hamanpaul/arc-conventions")


# --- distribution.yml attestation is anchored to the manifest, not the
# wheel RECORD (issue #63 CI regression): `manager._write_distribution_
# identity` overwrites `policy_check/data/distribution.yml` at install
# time, so its installed bytes never match the wheel's own RECORD entry
# by construction. `verify_installed_wheel_payload` must check that one
# path against `verification.canonical_distribution_identity(manifest
# ["distribution"])` instead of the RECORD size/sha256 it uses for every
# other file. Fixture style follows
# `test_installed_wheel_payload_attests_imported_files` in
# tests/test_preflight.py (build a real wheel zip with a real RECORD).


def _wheel_record_digest(content: bytes) -> str:
    encoded = base64.urlsafe_b64encode(hashlib.sha256(content).digest())
    return encoded.decode("ascii").rstrip("=")


def _write_installed_wheel(
    bundle_root: Path,
    installed_root: Path,
    *,
    wheel_name: str,
    distribution_name: str,
    version: str,
    files: dict[str, bytes],
) -> Path:
    dist_info = f"{distribution_name.replace('-', '_')}-{version}.dist-info"
    metadata_name = f"{dist_info}/METADATA"
    metadata = f"Name: {distribution_name}\nVersion: {version}\n".encode()
    payload = {**files, metadata_name: metadata}
    for name, content in payload.items():
        path = installed_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    record_name = f"{dist_info}/RECORD"
    record = "".join(
        f"{name},sha256={_wheel_record_digest(content)},{len(content)}\n"
        for name, content in payload.items()
    ) + f"{record_name},,\n"
    wheel = bundle_root / "wheels" / wheel_name
    wheel.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(wheel, mode="w") as archive:
        for name, content in payload.items():
            archive.writestr(name, content)
        archive.writestr(record_name, record)
    return wheel


_DISTRIBUTION_FIXTURE = {
    "canonical_org": "hamanpaul",
    "engine_repo": "hamanpaul/arc-conventions",
    "remote_base": "https://github.com",
    "distribution_name": "arc-conventions",
    "provider": "github",
}


def test_verify_installed_wheel_payload_accepts_distribution_identity_anchored_to_manifest(
    tmp_path: Path,
) -> None:
    """(a) Installed `distribution.yml` bytes equal the manifest's
    canonical serialization but diverge from the wheel's own RECORD entry
    (exactly what `manager._write_distribution_identity` leaves behind)
    -> verification succeeds.
    """
    bundle_root = tmp_path / "bundle"
    installed_root = tmp_path / "site-packages"
    wheel = _write_installed_wheel(
        bundle_root,
        installed_root,
        wheel_name="policy_check-1.0.15-py3-none-any.whl",
        distribution_name="policy-check",
        version="1.0.15",
        files={
            "policy_check/__init__.py": b"",
            "policy_check/data/distribution.yml": (
                b"# wheel-shipped default identity; never kept as-is\n"
                b"canonical_org: hamanpaul\n"
            ),
        },
    )
    # Simulate the install-time overwrite: its bytes now disagree with the
    # wheel's own RECORD entry above.
    (installed_root / "policy_check" / "data" / "distribution.yml").write_bytes(
        verification.canonical_distribution_identity(
            _DISTRIBUTION_FIXTURE
        ).encode("utf-8")
    )
    manifest = {
        "distribution": _DISTRIBUTION_FIXTURE,
        "wheels": [{"path": f"wheels/{wheel.name}", "sha256": "a" * 64}],
    }
    verified = verification.verify_installed_wheel_payload(
        bundle_root,
        installed_root,
        manifest,
        expected_repository="hamanpaul/arc-conventions",
    )
    assert verified is manifest


def test_verify_installed_wheel_payload_rejects_distribution_identity_mismatch(
    tmp_path: Path,
) -> None:
    """(b) Installed `distribution.yml` disagrees with the manifest's
    `distribution` block -> BundleError.
    """
    bundle_root = tmp_path / "bundle"
    installed_root = tmp_path / "site-packages"
    wheel = _write_installed_wheel(
        bundle_root,
        installed_root,
        wheel_name="policy_check-1.0.15-py3-none-any.whl",
        distribution_name="policy-check",
        version="1.0.15",
        files={
            "policy_check/__init__.py": b"",
            "policy_check/data/distribution.yml": b"# wheel-shipped default\n",
        },
    )
    (installed_root / "policy_check" / "data" / "distribution.yml").write_bytes(
        verification.canonical_distribution_identity(_DISTRIBUTION_FIXTURE).encode(
            "utf-8"
        )
        + b"\ntampered\n"
    )
    manifest = {
        "distribution": _DISTRIBUTION_FIXTURE,
        "wheels": [{"path": f"wheels/{wheel.name}", "sha256": "a" * 64}],
    }
    with pytest.raises(
        verification.BundleError, match="installed distribution identity"
    ):
        verification.verify_installed_wheel_payload(
            bundle_root,
            installed_root,
            manifest,
            expected_repository="hamanpaul/arc-conventions",
        )


def test_verify_installed_wheel_payload_fails_closed_without_manifest_distribution(
    tmp_path: Path,
) -> None:
    """(c) The manifest has no `distribution` block at all and the
    installed file disagrees with the wheel RECORD (the historical RECORD
    size/sha256 comparison this file used to go through would also
    reject it) -> BundleError raised fail-closed rather than silently
    falling back to a RECORD comparison.
    """
    bundle_root = tmp_path / "bundle"
    installed_root = tmp_path / "site-packages"
    wheel = _write_installed_wheel(
        bundle_root,
        installed_root,
        wheel_name="policy_check-1.0.15-py3-none-any.whl",
        distribution_name="policy-check",
        version="1.0.15",
        files={
            "policy_check/__init__.py": b"",
            "policy_check/data/distribution.yml": b"# wheel-shipped default\n",
        },
    )
    (installed_root / "policy_check" / "data" / "distribution.yml").write_bytes(
        verification.canonical_distribution_identity(_DISTRIBUTION_FIXTURE).encode(
            "utf-8"
        )
    )
    manifest = {
        "wheels": [{"path": f"wheels/{wheel.name}", "sha256": "a" * 64}],
    }
    with pytest.raises(verification.BundleError, match="distribution identity"):
        verification.verify_installed_wheel_payload(
            bundle_root,
            installed_root,
            manifest,
            expected_repository="hamanpaul/arc-conventions",
        )


def test_canonical_distribution_identity_fails_closed_on_missing_key() -> None:
    """(d) `canonical_distribution_identity` itself fails closed when a
    required field is missing from the `distribution` mapping.
    """
    incomplete = dict(_DISTRIBUTION_FIXTURE)
    del incomplete["provider"]
    with pytest.raises(verification.BundleError, match="provider"):
        verification.canonical_distribution_identity(incomplete)
    with pytest.raises(verification.BundleError, match="distribution identity"):
        verification.canonical_distribution_identity(None)
    with pytest.raises(verification.BundleError, match="distribution identity"):
        verification.canonical_distribution_identity({})
