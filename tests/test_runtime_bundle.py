from __future__ import annotations

import json
import io
import os
import subprocess
import sys
import sysconfig
import tarfile
from pathlib import Path

import pytest

from policy_check.runtime_bundle import builder, integrity, manager


def _fake_bundle(root: Path, version: str = "1.0.13") -> Path:
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
        "repository": integrity.CANONICAL_REPOSITORY,
        "release_tag": f"v{version}",
        "release_commit": "a" * 40,
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
        },
        "runtime_compatibility": {
            "implementation": sys.implementation.name,
            "python": f"{sys.version_info.major}.{sys.version_info.minor}",
            "platform": sysconfig.get_platform(),
        },
        "prerequisites": [
            f"python=={sys.version_info.major}.{sys.version_info.minor}",
            f"platform=={sysconfig.get_platform()}",
            "git",
            "sha256sum",
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
    (release / "venv" / ("Scripts" if os.name == "nt" else "bin")).mkdir(parents=True)
    (release / "VERIFIED").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "policy_version": version,
                "manifest_sha256": integrity.sha256_file(artifact / "manifest.json"),
            }
        ),
        encoding="utf-8",
    )
    return release


def test_verify_bundle_accepts_closed_file_set(tmp_path: Path) -> None:
    bundle = _fake_bundle(tmp_path)
    manifest = integrity.load_and_verify_bundle(bundle)
    assert manifest["policy_version"] == "1.0.13"
    assert manager.verify_bundle(bundle)["skill_version"] == "1.0.13"


def test_verify_bundle_accepts_fix_suffix_as_post_package_version(
    tmp_path: Path,
) -> None:
    bundle = _fake_bundle(tmp_path, "1.0.13-fix.2")
    manifest = integrity.load_and_verify_bundle(bundle)
    assert manifest["policy_version"] == "1.0.13-fix.2"
    assert manifest["package"]["version"] == "1.0.13.post2"
    assert manager.verify_bundle(bundle)["package"]["version"] == "1.0.13.post2"


@pytest.mark.parametrize(
    "relative",
    [
        "wheels/policy_check-1.0.13-py3-none-any.whl",
        "skills/preflight-ci/SKILL.md",
        "runtime/runtime_manager.py",
        "manifest.json",
    ],
)
def test_verify_bundle_rejects_payload_tamper(tmp_path: Path, relative: str) -> None:
    bundle = _fake_bundle(tmp_path)
    with (bundle / relative).open("ab") as stream:
        stream.write(b"tampered")
    with pytest.raises(integrity.BundleError, match="checksum mismatch"):
        integrity.load_and_verify_bundle(bundle)
    with pytest.raises(manager.RuntimeBundleError, match="checksum mismatch"):
        manager.verify_bundle(bundle)


def test_verify_bundle_rejects_unlisted_file_and_symlink(tmp_path: Path) -> None:
    bundle = _fake_bundle(tmp_path)
    (bundle / "extra").write_text("unlisted\n", encoding="utf-8")
    with pytest.raises(integrity.BundleError, match="file set mismatch"):
        integrity.load_and_verify_bundle(bundle)
    (bundle / "extra").unlink()
    (bundle / "escape").symlink_to("../outside")
    with pytest.raises(integrity.BundleError, match="symlink"):
        integrity.load_and_verify_bundle(bundle)


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
    assert integrity.load_and_verify_bundle(extracted)["policy_version"] == "1.0.13"
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

    def fake_run(argv, **_kwargs):
        python = Path(argv[0])
        return python.parents[2].name

    monkeypatch.setattr(manager, "_run", fake_run)
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
    selected, _manifest = manager.select_release(runtime_root, repo)
    assert selected == expected


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
            _venv = Path(path) / ("Scripts" if os.name == "nt" else "bin")
            _venv.mkdir(parents=True)
            (_venv / ("python.exe" if os.name == "nt" else "python")).write_text(
                "# fake\n",
                encoding="utf-8",
            )

    monkeypatch.setattr(manager.venv, "EnvBuilder", FakeEnvBuilder)
    monkeypatch.setattr(manager, "_run", lambda *_a, **_kw: "")
    monkeypatch.setattr(manager, "_smoke", lambda *_a, **_kw: None)

    assert manager.install(first, runtime_root, skill_target) == "1.0.13"
    assert manager.install(second, runtime_root, skill_target) == "1.0.14"
    assert (runtime_root / "current").resolve().name == "1.0.14"
    assert skill_target.is_symlink()
    assert manager.rollback(runtime_root, skill_target, None) == "1.0.13"
    assert (runtime_root / "current").resolve().name == "1.0.13"
    manager.uninstall(runtime_root, "1.0.14")
    assert not (runtime_root / "releases" / "1.0.14").exists()


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
    runtime_root = tmp_path / 'runtime-$("unsafe")'
    manager._install_launcher(runtime_root)
    text = (runtime_root / "bin" / "policy-preflight").read_text(encoding="utf-8")
    assert str(runtime_root) not in text
    assert 'dirname "${BASH_SOURCE[0]}"' in text
    assert 'TARGET_REPO="$PWD"' in text
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
