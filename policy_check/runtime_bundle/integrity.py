from __future__ import annotations

import hashlib
import json
import os
import re
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA_VERSION = 1
CANONICAL_REPOSITORY = "hamanpaul/paulsha-conventions"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:-fix\.\d+)?$")
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
BUNDLE_ROOT_RE = re.compile(
    r"^paulsha-conventions-v\d+\.\d+\.\d+(?:-fix\.\d+)?$"
)


class BundleError(RuntimeError):
    """The bundle is unsafe, incomplete, or inconsistent."""


def normalized_package_version(value: str) -> str:
    return re.sub(r"-fix\.(\d+)$", r".post\1", value)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_relative_path(value: object, *, field: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise BundleError(f"{field} must be a non-empty relative path")
    if "\\" in value or "\x00" in value:
        raise BundleError(f"{field} contains an unsafe separator")
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise BundleError(f"{field} contains traversal or dot segments")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise BundleError(f"{field} contains traversal or dot segments")
    return path


def tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise BundleError(f"symlink is not allowed in bundle payload: {path}")
        if path.is_file():
            files.append(path)
    for path in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _parse_checksums(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise BundleError("SHA256SUMS is unreadable") from exc
    entries: dict[str, str] = {}
    for line_number, line in enumerate(lines, start=1):
        if not line:
            continue
        if "  " not in line:
            raise BundleError(f"invalid SHA256SUMS line {line_number}")
        digest, raw_name = line.split("  ", 1)
        relative = safe_relative_path(raw_name, field=f"SHA256SUMS line {line_number}")
        name = relative.as_posix()
        if SHA256_RE.fullmatch(digest) is None:
            raise BundleError(f"invalid SHA-256 at line {line_number}")
        if name in entries:
            raise BundleError(f"duplicate checksum entry: {name}")
        entries[name] = digest
    if not entries:
        raise BundleError("SHA256SUMS is empty")
    return entries


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BundleError("manifest.json is unreadable or invalid JSON") from exc
    if not isinstance(payload, dict):
        raise BundleError("manifest.json must contain an object")
    return payload


def _require_manifest_shape(manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise BundleError("unsupported manifest schema_version")
    version = manifest.get("policy_version")
    if not isinstance(version, str) or VERSION_RE.fullmatch(version) is None:
        raise BundleError("manifest policy_version is invalid")
    if manifest.get("skill_version") != version:
        raise BundleError("skill_version does not match policy_version")
    if manifest.get("repository") != CANONICAL_REPOSITORY:
        raise BundleError("manifest repository is not canonical")
    if manifest.get("release_tag") != f"v{version}":
        raise BundleError("release_tag does not match policy_version")
    if FULL_SHA_RE.fullmatch(str(manifest.get("release_commit") or "")) is None:
        raise BundleError("release_commit must be a full lowercase SHA")
    package = manifest.get("package")
    if (
        not isinstance(package, dict)
        or package.get("name") != "policy-check"
        or package.get("version") != normalized_package_version(version)
        or not isinstance(package.get("requires_python"), str)
    ):
        raise BundleError("package identity does not match policy_version")
    wheels = manifest.get("wheels")
    if not isinstance(wheels, list) or not wheels:
        raise BundleError("manifest wheels must be a non-empty list")
    for index, wheel in enumerate(wheels):
        if not isinstance(wheel, dict):
            raise BundleError(f"manifest wheels[{index}] must be an object")
        safe_relative_path(wheel.get("path"), field=f"wheels[{index}].path")
        if SHA256_RE.fullmatch(str(wheel.get("sha256") or "")) is None:
            raise BundleError(f"wheels[{index}].sha256 is invalid")
    skill = manifest.get("skill")
    if not isinstance(skill, dict):
        raise BundleError("manifest skill must be an object")
    safe_relative_path(skill.get("path"), field="skill.path")
    if SHA256_RE.fullmatch(str(skill.get("sha256") or "")) is None:
        raise BundleError("skill.sha256 is invalid")
    runtime = manifest.get("runtime")
    if not isinstance(runtime, dict):
        raise BundleError("manifest runtime must be an object")
    safe_relative_path(runtime.get("path"), field="runtime.path")
    if SHA256_RE.fullmatch(str(runtime.get("sha256") or "")) is None:
        raise BundleError("runtime.sha256 is invalid")
    compatibility = manifest.get("runtime_compatibility")
    if (
        not isinstance(compatibility, dict)
        or re.fullmatch(
            r"[a-z][a-z0-9_]*",
            str(compatibility.get("implementation") or ""),
        )
        is None
        or re.fullmatch(r"\d+\.\d+", str(compatibility.get("python") or "")) is None
        or not isinstance(compatibility.get("abi"), str)
        or not compatibility["abi"]
        or not isinstance(compatibility.get("platform"), str)
        or not compatibility["platform"]
    ):
        raise BundleError("runtime_compatibility is invalid")
    prerequisites = manifest.get("prerequisites")
    if not isinstance(prerequisites, list) or not all(
        isinstance(item, str) and item for item in prerequisites
    ):
        raise BundleError("manifest prerequisites must be a list of strings")


def load_and_verify_bundle(bundle_root: Path) -> dict[str, Any]:
    root = bundle_root.resolve()
    checksums_path = root / "SHA256SUMS"
    manifest_path = root / "manifest.json"
    if checksums_path.is_symlink() or manifest_path.is_symlink():
        raise BundleError("bundle metadata must not be symlinks")
    checksums = _parse_checksums(checksums_path)

    actual_files: set[str] = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise BundleError(f"bundle contains a symlink: {path.relative_to(root)}")
        if path.is_file() and path != checksums_path:
            actual_files.add(path.relative_to(root).as_posix())
    expected_files = set(checksums)
    if actual_files != expected_files:
        missing = sorted(expected_files - actual_files)
        extra = sorted(actual_files - expected_files)
        raise BundleError(f"bundle file set mismatch: missing={missing} extra={extra}")
    for name, expected in checksums.items():
        path = root / name
        if not path.is_file() or path.is_symlink():
            raise BundleError(f"checksummed payload is not a regular file: {name}")
        if sha256_file(path) != expected:
            raise BundleError(f"checksum mismatch: {name}")

    manifest = _read_manifest(manifest_path)
    _require_manifest_shape(manifest)
    for wheel in manifest["wheels"]:
        wheel_path = safe_relative_path(wheel["path"], field="wheel.path").as_posix()
        if checksums.get(wheel_path) != wheel["sha256"]:
            raise BundleError(f"wheel manifest/checksum mismatch: {wheel_path}")
    skill = manifest["skill"]
    skill_root = root / safe_relative_path(skill["path"], field="skill.path")
    if not skill_root.is_dir() or tree_sha256(skill_root) != skill["sha256"]:
        raise BundleError("skill payload hash mismatch")
    runtime = manifest["runtime"]
    runtime_path = root / safe_relative_path(runtime["path"], field="runtime.path")
    if not runtime_path.is_file() or sha256_file(runtime_path) != runtime["sha256"]:
        raise BundleError("runtime manager hash mismatch")
    return manifest


def write_checksums(root: Path) -> None:
    files = [
        path
        for path in root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    ]
    lines = [
        f"{sha256_file(path)}  {path.relative_to(root).as_posix()}"
        for path in sorted(files, key=lambda item: item.relative_to(root).as_posix())
    ]
    (root / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def extract_verified_archive(
    archive: Path,
    output_dir: Path,
    expected_sha256: str,
) -> Path:
    source = archive.resolve()
    if SHA256_RE.fullmatch(expected_sha256) is None:
        raise BundleError("expected archive SHA-256 is invalid")
    if not source.is_file() or source.is_symlink():
        raise BundleError("bundle archive must be a regular file")
    if sha256_file(source) != expected_sha256:
        raise BundleError("archive SHA-256 mismatch")

    destination = output_dir.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    roots: set[str] = set()
    names: set[str] = set()
    try:
        with tarfile.open(source, mode="r:gz") as bundle_tar:
            members = bundle_tar.getmembers()
            if not members:
                raise BundleError("bundle archive is empty")
            for member in members:
                relative = safe_relative_path(member.name, field="archive member")
                name = relative.as_posix()
                if name in names:
                    raise BundleError(f"duplicate archive member: {name}")
                names.add(name)
                roots.add(relative.parts[0])
                if not (member.isdir() or member.isfile()):
                    raise BundleError(f"unsafe archive member type: {name}")
            if len(roots) != 1:
                raise BundleError("archive must contain exactly one bundle root")
            root_name = next(iter(roots))
            if BUNDLE_ROOT_RE.fullmatch(root_name) is None:
                raise BundleError("archive bundle root name is invalid")
            target = destination / root_name
            if target.exists() or target.is_symlink():
                raise BundleError(f"archive destination already exists: {target}")
            with tempfile.TemporaryDirectory(
                prefix=".runtime-extract-",
                dir=destination,
            ) as temporary:
                stage = Path(temporary)
                bundle_tar.extractall(stage, filter="data")
                extracted = stage / root_name
                load_and_verify_bundle(extracted)
                os.replace(extracted, target)
    except (OSError, tarfile.TarError) as exc:
        raise BundleError("bundle archive is unreadable or unsafe") from exc
    return target


def atomic_symlink(target: Path, link: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    temporary = link.with_name(f".{link.name}.tmp-{os.getpid()}")
    if temporary.exists() or temporary.is_symlink():
        temporary.unlink()
    temporary.symlink_to(target)
    os.replace(temporary, link)
