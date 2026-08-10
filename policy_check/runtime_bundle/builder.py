from __future__ import annotations

import gzip
import json
import os
import re
import shutil
import subprocess
import sys
import sysconfig
import tarfile
import tempfile
import tomllib
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Sequence

from policy_check.identity import identity

from .integrity import (
    BundleError,
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
command -v "$PYTHON_BIN" >/dev/null 2>&1 || {
  echo "ERROR: Python 3.11+ is required to install this runtime bundle" >&2
  exit 2
}
"$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' || {
  echo "ERROR: Python 3.11+ is required to install this runtime bundle" >&2
  exit 2
}
"$PYTHON_BIN" -I -m ensurepip --version >/dev/null 2>&1 || {
  echo "ERROR: Python venv/ensurepip support is required; install python3-venv" >&2
  exit 2
}
"$PYTHON_BIN" -I - "$BUNDLE_ROOT/manifest.json" <<'PY' || exit 2
import json
import shutil
import subprocess
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as stream:
        manifest = json.load(stream)
except (OSError, UnicodeError, json.JSONDecodeError):
    print("ERROR: verified bundle manifest is unreadable", file=sys.stderr)
    raise SystemExit(2)
if not isinstance(manifest, dict) or not isinstance(
    manifest.get("prerequisites"),
    list,
):
    print("ERROR: verified bundle manifest prerequisites are invalid", file=sys.stderr)
    raise SystemExit(2)
checks = {
    "git": ("git", ["--version"]),
    "sha256sum": ("sha256sum", ["--version"]),
    "universal-ctags": ("ctags", ["--output-format=json", "--version"]),
}
missing = []
for prerequisite in manifest.get("prerequisites", []):
    if not isinstance(prerequisite, str):
        print(
            "ERROR: verified bundle manifest prerequisites are invalid",
            file=sys.stderr,
        )
        raise SystemExit(2)
    if prerequisite not in checks:
        continue
    command, arguments = checks[prerequisite]
    executable = shutil.which(command)
    if executable is None:
        missing.append(f"{prerequisite} ({command})")
        continue
    try:
        result = subprocess.run(
            [executable, *arguments],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        missing.append(f"{prerequisite} ({command})")
        continue
    if result.returncode != 0:
        missing.append(f"{prerequisite} ({command})")
if missing:
    print(
        "ERROR: runtime install prerequisites unavailable: " + ", ".join(missing),
        file=sys.stderr,
    )
    raise SystemExit(2)
PY
exec "$PYTHON_BIN" -I -B "$BUNDLE_ROOT/runtime/runtime_manager.py" \
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
    return remote in identity().remote_urls()


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
                    info.mode = (
                        0o755
                        if info.isdir()
                        or (info.isfile() and path.stat().st_mode & 0o111)
                        else 0o644
                    )
                    info.pax_headers = {}
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
            if sys.version_info >= (3, 11, 4):
                source_tar.extractall(snapshot, filter="data")
            else:
                # Members were already restricted to safe relative paths.
                source_tar.extractall(snapshot)
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


def _normalize_distribution_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _validate_runtime_constraints(snapshot: Path) -> dict[str, str]:
    pyproject = snapshot / "pyproject.toml"
    constraints = (
        snapshot / "policy_check" / "runtime_bundle" / "constraints.txt"
    )
    try:
        project = tomllib.loads(pyproject.read_text(encoding="utf-8")).get(
            "project",
            {},
        )
        dependency_values = project.get("dependencies", [])
        constraint_lines = constraints.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise BundleError("runtime dependency inputs are unreadable") from exc
    if not isinstance(dependency_values, list) or not all(
        isinstance(item, str) for item in dependency_values
    ):
        raise BundleError("[project].dependencies must be a list of strings")

    required: set[str] = set()
    for dependency in dependency_values:
        match = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", dependency)
        if match is None:
            raise BundleError(f"cannot parse project dependency: {dependency}")
        required.add(_normalize_distribution_name(match.group(1)))

    locked: dict[str, str] = {}
    for raw_line in constraint_lines:
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        match = re.fullmatch(
            r"([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9.!+_-]*)",
            line,
        )
        if match is None:
            raise BundleError(
                "runtime constraints must use one exact name==version per line"
            )
        name = _normalize_distribution_name(match.group(1))
        if name in locked:
            raise BundleError(f"duplicate runtime constraint: {name}")
        locked[name] = match.group(2)

    missing = sorted(required - set(locked))
    if missing:
        raise BundleError(
            "runtime constraints do not lock project dependencies: "
            + ", ".join(missing)
        )
    return locked


def _validate_resolved_wheel_constraints(
    wheels: Path,
    constraints: dict[str, str],
) -> None:
    resolved: dict[str, str] = {}
    for wheel in sorted(wheels.glob("*.whl")):
        metadata = _wheel_metadata(wheel)
        name = metadata.get("Name")
        version = metadata.get("Version")
        if not name or not version:
            raise BundleError(f"wheel metadata lacks Name/Version: {wheel.name}")
        normalized = _normalize_distribution_name(name)
        if normalized in resolved:
            raise BundleError(f"duplicate resolved wheel distribution: {normalized}")
        resolved[normalized] = version

    dependencies = {
        name: version
        for name, version in resolved.items()
        if name != "policy-check"
    }
    unlocked = sorted(set(dependencies) - set(constraints))
    if unlocked:
        raise BundleError(
            "resolved dependency wheels lack exact constraints: "
            + ", ".join(unlocked)
        )
    mismatched = sorted(
        name
        for name, version in dependencies.items()
        if constraints[name] != version
    )
    if mismatched:
        details = ", ".join(
            f"{name}=={dependencies[name]} (constraint {constraints[name]})"
            for name in mismatched
        )
        raise BundleError(f"resolved dependency wheel violates constraint: {details}")


def _prepare_output_directory(source: Path, output_dir: Path) -> Path:
    destination = output_dir.resolve()
    try:
        destination.relative_to(source.resolve())
    except ValueError:
        pass
    else:
        raise BundleError("output directory must be outside the source repository")
    destination.mkdir(parents=True, exist_ok=True)
    return destination


_VENDORED_EXPECTED_REPOSITORY_PLACEHOLDER = (
    "_VENDORED_EXPECTED_REPOSITORY: str | None = None"
)


def _vendor_runtime_manager(
    source: Path,
    destination: Path,
    *,
    expected_repository: str,
) -> None:
    """Copy `manager.py` into a bundle as `runtime_manager.py`, baking in
    the distribution's expected repository as a build-time constant.

    The vendored copy runs standalone (`python3 -I`/`-P`) where
    `policy_check.identity` is not importable, so it cannot resolve its own
    expected repository at runtime. Baking the value in here — rather than
    letting the vendored copy read it back out of the bundle's own
    `manifest.json` — keeps the manifest `repository` check from being
    self-referential: the constant lives in this sibling file, whose own
    checksum is independently pinned by `manifest["runtime"]["sha256"]` and,
    once activated, by the deployed launcher script's embedded checksum.
    """
    text = source.read_text(encoding="utf-8")
    if text.count(_VENDORED_EXPECTED_REPOSITORY_PLACEHOLDER) != 1:
        raise BundleError(
            "runtime manager source is missing the expected vendoring placeholder"
        )
    destination.write_text(
        text.replace(
            _VENDORED_EXPECTED_REPOSITORY_PLACEHOLDER,
            "_VENDORED_EXPECTED_REPOSITORY: str | None = "
            f"{expected_repository!r}",
        ),
        encoding="utf-8",
    )
    shutil.copymode(source, destination)


def build_bundle(repo: Path, output_dir: Path, tag: str) -> tuple[Path, str]:
    source = repo.resolve()
    version, commit, epoch = attest_clean_tag(source, tag)
    destination = _prepare_output_directory(source, output_dir)
    archive = destination / f"{identity().distribution_name}-v{version}.tar.gz"
    digest_file = archive.with_suffix(archive.suffix + ".sha256")
    if archive.exists() or digest_file.exists():
        raise BundleError(f"output already exists: {archive}")

    with tempfile.TemporaryDirectory(
        prefix=".runtime-bundle-",
        dir=destination,
    ) as temporary:
        temp = Path(temporary)
        snapshot = _tag_snapshot(source, tag, temp)
        _prepare_package_version(snapshot, version)
        constraints = _validate_runtime_constraints(snapshot)
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
                "--constraint",
                str(snapshot / "policy_check" / "runtime_bundle" / "constraints.txt"),
                "--dest",
                str(wheels),
                str(built[0]),
            ],
            cwd=snapshot,
        )
        if any(path.suffix != ".whl" for path in wheels.iterdir()):
            raise BundleError("dependency closure contains a non-wheel artifact")
        _validate_resolved_wheel_constraints(wheels, constraints)
        main_wheel = wheels / built[0].name
        metadata = _wheel_metadata(main_wheel)
        if (
            metadata.get("Name") != "policy-check"
            or metadata.get("Version") != normalized_package_version(version)
        ):
            raise BundleError("wheel metadata does not match VERSION")

        bundle = temp / f"{identity().distribution_name}-v{version}"
        bundle.mkdir()
        shutil.move(str(wheels), bundle / "wheels")
        skill_root = bundle / "skills" / "preflight-ci"
        shutil.copytree(snapshot / "skills" / "preflight-ci", skill_root)
        runtime_dir = bundle / "runtime"
        runtime_dir.mkdir()
        manager_source = snapshot / "policy_check" / "runtime_bundle" / "manager.py"
        verifier_source = (
            snapshot / "policy_check" / "runtime_bundle" / "verification.py"
        )
        if not manager_source.is_file() or not verifier_source.is_file():
            raise BundleError("tag snapshot is missing runtime bootstrap sources")
        _vendor_runtime_manager(
            manager_source,
            runtime_dir / "runtime_manager.py",
            expected_repository=identity().engine_repo,
        )
        shutil.copy2(verifier_source, runtime_dir / "runtime_verifier.py")
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
            "repository": identity().engine_repo,
            "release_tag": tag,
            "release_commit": commit,
            "distribution": {
                "canonical_org": identity().canonical_org,
                "engine_repo": identity().engine_repo,
                "remote_base": identity().remote_base,
                "distribution_name": identity().distribution_name,
                "provider": identity().provider,
                **(
                    {"distribution_build": identity().distribution_build}
                    if identity().distribution_build is not None
                    else {}
                ),
            },
            "wheels": wheel_entries,
            "skill": {
                "path": "skills/preflight-ci",
                "sha256": tree_sha256(skill_root),
            },
            "runtime": {
                "path": "runtime/runtime_manager.py",
                "sha256": sha256_file(runtime_dir / "runtime_manager.py"),
                "verifier_path": "runtime/runtime_verifier.py",
                "verifier_sha256": sha256_file(
                    runtime_dir / "runtime_verifier.py"
                ),
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
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        write_checksums(bundle)
        load_and_verify_bundle(bundle, expected_repository=identity().engine_repo)
        temporary_archive = temp / archive.name
        _deterministic_archive(bundle, temporary_archive, epoch=epoch)
        os.replace(temporary_archive, archive)

    digest = sha256_file(archive)
    digest_file.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    return archive, digest
