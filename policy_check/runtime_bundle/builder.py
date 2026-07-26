from __future__ import annotations

import gzip
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Sequence

from .integrity import (
    BundleError,
    CANONICAL_REPOSITORY,
    load_and_verify_bundle,
    normalized_package_version,
    sha256_file,
    tree_sha256,
    write_checksums,
)


INSTALLER = """#!/usr/bin/env bash
set -euo pipefail
BUNDLE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
command -v sha256sum >/dev/null 2>&1 || {
  echo "ERROR: sha256sum is required" >&2
  exit 2
}
(cd "$BUNDLE_ROOT" && sha256sum --check --strict SHA256SUMS)
PYTHON_BIN="${PYTHON_BIN:-python3}"
exec "$PYTHON_BIN" -P "$BUNDLE_ROOT/runtime/runtime_manager.py" \
  install --bundle "$BUNDLE_ROOT" "$@"
"""


def _run(argv: Sequence[str], *, cwd: Path, env: dict[str, str] | None = None) -> str:
    try:
        result = subprocess.run(
            list(argv),
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, UnicodeError) as exc:
        raise BundleError(f"command unavailable: {argv[0]}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        suffix = f": {detail[-1]}" if detail else ""
        raise BundleError(
            f"command failed ({result.returncode}): {' '.join(argv)}{suffix}"
        )
    return result.stdout.strip()


def _git(repo: Path, *args: str) -> str:
    return _run(["git", *args], cwd=repo)


def _canonical_remote(value: str) -> bool:
    remote = value.strip().removesuffix(".git")
    return remote in {
        f"https://github.com/{CANONICAL_REPOSITORY}",
        f"ssh://git@github.com/{CANONICAL_REPOSITORY}",
        f"git@github.com:{CANONICAL_REPOSITORY}",
    }


def attest_clean_tag(repo: Path, tag: str) -> tuple[str, str, int]:
    version = (repo / "VERSION").read_text(encoding="utf-8").strip()
    if tag != f"v{version}":
        raise BundleError("tag does not match VERSION")
    if not _canonical_remote(_git(repo, "remote", "get-url", "origin")):
        raise BundleError("origin is not the canonical repository")
    if _git(repo, "status", "--porcelain", "--untracked-files=all"):
        raise BundleError("source checkout is not clean")
    head = _git(repo, "rev-parse", "HEAD")
    if _git(repo, "rev-parse", f"{tag}^{{commit}}") != head:
        raise BundleError("tag does not resolve to HEAD")
    if _git(repo, "cat-file", "-t", tag) != "tag":
        raise BundleError("release tag must be annotated")
    commit_epoch = int(_git(repo, "show", "-s", "--format=%ct", head))
    return version, head, commit_epoch


def _wheel_metadata(wheel: Path) -> dict[str, str]:
    try:
        with zipfile.ZipFile(wheel) as archive:
            names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
            if len(names) != 1:
                raise BundleError(f"wheel has ambiguous METADATA: {wheel.name}")
            lines = archive.read(names[0]).decode("utf-8").splitlines()
    except (OSError, UnicodeError, zipfile.BadZipFile) as exc:
        raise BundleError(f"cannot inspect wheel: {wheel.name}") from exc
    fields: dict[str, str] = {}
    for line in lines:
        if ": " in line:
            key, value = line.split(": ", 1)
            fields.setdefault(key, value)
    return fields


def _deterministic_archive(source: Path, archive: Path, *, epoch: int) -> None:
    root_name = source.name
    with archive.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as tar:
                entries = [source, *source.rglob("*")]
                for path in sorted(
                    entries,
                    key=lambda item: (
                        item != source,
                        item.relative_to(source).as_posix() if item != source else "",
                    ),
                ):
                    if path.is_symlink():
                        raise BundleError("bundle archive cannot contain symlinks")
                    arcname = (
                        root_name
                        if path == source
                        else f"{root_name}/{path.relative_to(source).as_posix()}"
                    )
                    info = tar.gettarinfo(str(path), arcname)
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    info.mtime = epoch
                    if info.isfile():
                        with path.open("rb") as stream:
                            tar.addfile(info, stream)
                    else:
                        tar.addfile(info)


def _tag_snapshot(repo: Path, tag: str, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    snapshot = destination / "source"
    archive = destination / "source.tar"
    _run(
        ["git", "archive", "--format=tar", "--output", str(archive), tag],
        cwd=repo,
    )
    snapshot.mkdir()
    try:
        with tarfile.open(archive, mode="r:") as source_tar:
            for member in source_tar.getmembers():
                path = PurePosixPath(member.name)
                if (
                    path.is_absolute()
                    or any(part in {"", ".", ".."} for part in path.parts)
                ):
                    raise BundleError("git archive contains an unsafe member")
            source_tar.extractall(snapshot, filter="data")
    except (OSError, tarfile.TarError) as exc:
        raise BundleError("cannot extract clean tag snapshot") from exc
    return snapshot


def _prepare_package_version(snapshot: Path, policy_version: str) -> None:
    package_version = normalized_package_version(policy_version)
    if package_version == policy_version:
        return
    pyproject = snapshot / "pyproject.toml"
    try:
        lines = pyproject.read_text(encoding="utf-8").splitlines(keepends=True)
    except (OSError, UnicodeError) as exc:
        raise BundleError("tag snapshot pyproject.toml is unreadable") from exc
    in_project = False
    matches = 0
    expected = f'version = "{policy_version}"'
    replacement = f'version = "{package_version}"'
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_project = stripped == "[project]"
            continue
        if in_project and stripped == expected:
            newline = "\n" if line.endswith("\n") else ""
            lines[index] = replacement + newline
            matches += 1
    if matches != 1:
        raise BundleError(
            "tag snapshot [project] version does not match policy VERSION"
        )
    try:
        pyproject.write_text("".join(lines), encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise BundleError("cannot prepare package version in tag snapshot") from exc


def build_bundle(repo: Path, output_dir: Path, tag: str) -> tuple[Path, str]:
    source = repo.resolve()
    version, commit, epoch = attest_clean_tag(source, tag)
    destination = output_dir.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / f"paulsha-conventions-v{version}.tar.gz"
    digest_file = archive.with_suffix(archive.suffix + ".sha256")
    if archive.exists() or digest_file.exists():
        raise BundleError(f"output already exists: {archive}")

    with tempfile.TemporaryDirectory(prefix="runtime-bundle-") as temporary:
        temp = Path(temporary)
        snapshot = _tag_snapshot(source, tag, temp)
        _prepare_package_version(snapshot, version)
        wheel_build = temp / "wheel-build"
        wheels = temp / "wheels"
        wheel_build.mkdir()
        wheels.mkdir()
        env = dict(os.environ)
        env["SOURCE_DATE_EPOCH"] = str(epoch)
        _run(
            [
                sys.executable,
                "-m",
                "build",
                "--wheel",
                "--outdir",
                str(wheel_build),
                str(snapshot),
            ],
            cwd=snapshot,
            env=env,
        )
        built = sorted(wheel_build.glob("policy_check-*.whl"))
        if len(built) != 1:
            raise BundleError("expected exactly one policy-check wheel")
        shutil.copy2(built[0], wheels / built[0].name)
        _run(
            [
                sys.executable,
                "-m",
                "pip",
                "download",
                "--only-binary=:all:",
                "--dest",
                str(wheels),
                str(built[0]),
            ],
            cwd=snapshot,
        )
        if any(path.suffix != ".whl" for path in wheels.iterdir()):
            raise BundleError("dependency closure contains a non-wheel artifact")
        main_wheel = wheels / built[0].name
        metadata = _wheel_metadata(main_wheel)
        if (
            metadata.get("Name") != "policy-check"
            or metadata.get("Version") != normalized_package_version(version)
        ):
            raise BundleError("wheel metadata does not match VERSION")

        bundle = temp / f"paulsha-conventions-v{version}"
        bundle.mkdir()
        shutil.move(str(wheels), bundle / "wheels")
        skill_root = bundle / "skills" / "preflight-ci"
        shutil.copytree(snapshot / "skills" / "preflight-ci", skill_root)
        runtime_dir = bundle / "runtime"
        runtime_dir.mkdir()
        manager_source = snapshot / "policy_check" / "runtime_bundle" / "manager.py"
        if not manager_source.is_file():
            raise BundleError("tag snapshot is missing the runtime manager")
        shutil.copy2(manager_source, runtime_dir / "runtime_manager.py")
        installer = bundle / "install.sh"
        installer.write_text(INSTALLER, encoding="utf-8")
        installer.chmod(0o755)

        wheel_entries: list[dict[str, Any]] = []
        for wheel in sorted((bundle / "wheels").iterdir()):
            wheel_entries.append(
                {
                    "path": f"wheels/{wheel.name}",
                    "sha256": sha256_file(wheel),
                }
            )
        manifest = {
            "schema_version": 1,
            "policy_version": version,
            "skill_version": version,
            "package": {
                "name": "policy-check",
                "version": metadata["Version"],
                "requires_python": metadata.get("Requires-Python", ">=3.11"),
            },
            "repository": CANONICAL_REPOSITORY,
            "release_tag": tag,
            "release_commit": commit,
            "wheels": wheel_entries,
            "skill": {
                "path": "skills/preflight-ci",
                "sha256": tree_sha256(skill_root),
            },
            "runtime": {
                "path": "runtime/runtime_manager.py",
                "sha256": sha256_file(runtime_dir / "runtime_manager.py"),
            },
            "prerequisites": ["python>=3.11", "git", "sha256sum", "universal-ctags"],
        }
        (bundle / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        write_checksums(bundle)
        load_and_verify_bundle(bundle)
        _deterministic_archive(bundle, archive, epoch=epoch)

    digest = sha256_file(archive)
    digest_file.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    return archive, digest
