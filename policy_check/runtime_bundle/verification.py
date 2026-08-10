from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


# This module is deliberately stdlib-only. The source package and the vendored
# bootstrap manager both execute this exact verifier implementation.
SCHEMA_VERSION = 1
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:-fix\.\d+)?$")
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

# The relative path, inside the installed policy-check distribution, of the
# file the runtime manager overwrites at install time with the bundle's own
# distribution identity (see `manager._write_distribution_identity`). Its
# installed bytes can never match the wheel's built-in RECORD entry by
# construction, so `verify_installed_wheel_payload` verifies this one path
# against the manifest instead of the wheel RECORD (see
# `canonical_distribution_identity`).
DISTRIBUTION_IDENTITY_RECORD_PATH = "policy_check/data/distribution.yml"

# Single source of truth for the distribution-identity file's field order
# and "key: value\n" serialization. `manager._write_distribution_identity`
# (install time) and `verify_installed_wheel_payload` (attestation time)
# both call `canonical_distribution_identity` so the two can never drift.
DISTRIBUTION_IDENTITY_FIELDS = (
    "canonical_org",
    "engine_repo",
    "remote_base",
    "distribution_name",
    "provider",
)


class BundleError(RuntimeError):
    """The bundle is unsafe, incomplete, or inconsistent."""


def canonical_distribution_identity(dist: Any) -> str:
    """Render a manifest `distribution` mapping into the exact text the
    installed `policy_check/data/distribution.yml` must contain.

    Fail-closed: anything other than a `dict` with every
    `DISTRIBUTION_IDENTITY_FIELDS` key present raises `BundleError` rather
    than silently producing a partial or empty identity.
    """
    if not isinstance(dist, dict) or not dist:
        raise BundleError("bundle manifest is missing distribution identity")
    missing = [key for key in DISTRIBUTION_IDENTITY_FIELDS if key not in dist]
    if missing:
        raise BundleError(
            "bundle manifest distribution identity is missing: "
            + ", ".join(missing)
        )
    return "".join(f"{key}: {dist[key]}\n" for key in DISTRIBUTION_IDENTITY_FIELDS)


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


def _require_hashed_path(
    payload: dict[str, Any],
    *,
    path_field: str,
    hash_field: str,
) -> None:
    safe_relative_path(payload.get(path_field), field=f"runtime.{path_field}")
    if SHA256_RE.fullmatch(str(payload.get(hash_field) or "")) is None:
        raise BundleError(f"runtime.{hash_field} is invalid")


def _require_manifest_shape(manifest: dict[str, Any], expected_repository: str) -> None:
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise BundleError("unsupported manifest schema_version")
    version = manifest.get("policy_version")
    if not isinstance(version, str) or VERSION_RE.fullmatch(version) is None:
        raise BundleError("manifest policy_version is invalid")
    if manifest.get("skill_version") != version:
        raise BundleError("skill_version does not match policy_version")
    if manifest.get("repository") != expected_repository:
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
        or not package["requires_python"]
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
    _require_hashed_path(runtime, path_field="path", hash_field="sha256")
    _require_hashed_path(
        runtime,
        path_field="verifier_path",
        hash_field="verifier_sha256",
    )
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


def load_and_verify_bundle(bundle_root: Path, *, expected_repository: str) -> dict[str, Any]:
    root = bundle_root.resolve()
    checksums_path = root / "SHA256SUMS"
    manifest_path = root / "manifest.json"
    if (
        not checksums_path.is_file()
        or checksums_path.is_symlink()
        or not manifest_path.is_file()
        or manifest_path.is_symlink()
    ):
        raise BundleError("bundle metadata must be regular files")
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
    _require_manifest_shape(manifest, expected_repository)
    for wheel in manifest["wheels"]:
        wheel_path = safe_relative_path(wheel["path"], field="wheel.path").as_posix()
        if checksums.get(wheel_path) != wheel["sha256"]:
            raise BundleError(f"wheel manifest/checksum mismatch: {wheel_path}")
    skill = manifest["skill"]
    skill_root = root / safe_relative_path(skill["path"], field="skill.path")
    if not skill_root.is_dir() or tree_sha256(skill_root) != skill["sha256"]:
        raise BundleError("skill payload hash mismatch")
    runtime = manifest["runtime"]
    for path_field, hash_field in (
        ("path", "sha256"),
        ("verifier_path", "verifier_sha256"),
    ):
        relative = safe_relative_path(
            runtime[path_field],
            field=f"runtime.{path_field}",
        )
        runtime_path = root / relative
        if (
            not runtime_path.is_file()
            or runtime_path.is_symlink()
            or sha256_file(runtime_path) != runtime[hash_field]
        ):
            raise BundleError(f"runtime payload hash mismatch: {relative.as_posix()}")
    return manifest


def verify_installed_wheel_payload(
    bundle_root: Path,
    site_packages: Path,
    manifest: dict[str, Any] | None = None,
    *,
    expected_repository: str,
) -> dict[str, Any]:
    verified_manifest = (
        load_and_verify_bundle(bundle_root, expected_repository=expected_repository)
        if manifest is None
        else manifest
    )
    installed_root_input = site_packages
    if (
        not installed_root_input.is_dir()
        or installed_root_input.is_symlink()
    ):
        raise BundleError("installed site-packages must be a regular directory")
    installed_root = installed_root_input.resolve()
    executable_top_levels: set[str] = set()
    recorded_paths: set[str] = set()
    seen_distributions: set[str] = set()
    saw_policy_check = False

    for index, entry in enumerate(verified_manifest["wheels"]):
        wheel_relative = safe_relative_path(
            entry["path"],
            field=f"wheels[{index}].path",
        )
        wheel = bundle_root.resolve() / wheel_relative
        try:
            with zipfile.ZipFile(wheel) as archive:
                metadata_names = [
                    name
                    for name in archive.namelist()
                    if name.endswith(".dist-info/METADATA")
                ]
                record_names = [
                    name
                    for name in archive.namelist()
                    if name.endswith(".dist-info/RECORD")
                ]
                if len(metadata_names) != 1 or len(record_names) != 1:
                    raise BundleError(
                        f"wheel has ambiguous metadata/RECORD: {wheel.name}"
                    )
                metadata_root = metadata_names[0].removesuffix("METADATA")
                if record_names[0].removesuffix("RECORD") != metadata_root:
                    raise BundleError(
                        f"wheel metadata/RECORD disagree: {wheel.name}"
                    )
                metadata_text = archive.read(metadata_names[0]).decode("utf-8")
                rows = list(
                    csv.reader(
                        io.StringIO(
                            archive.read(record_names[0]).decode("utf-8")
                        )
                    )
                )
        except (OSError, UnicodeError, zipfile.BadZipFile) as exc:
            raise BundleError(f"cannot inspect verified wheel: {wheel.name}") from exc

        metadata_fields: dict[str, str] = {}
        for line in metadata_text.splitlines():
            if ": " in line:
                key, value = line.split(": ", 1)
                metadata_fields.setdefault(key, value)
        distribution_name = metadata_fields.get("Name")
        distribution_version = metadata_fields.get("Version")
        if not distribution_name or not distribution_version:
            raise BundleError(f"wheel lacks Name/Version: {wheel.name}")
        normalized_name = re.sub(r"[-_.]+", "-", distribution_name).lower()
        if normalized_name in seen_distributions:
            raise BundleError(
                f"duplicate installed wheel distribution: {normalized_name}"
            )
        seen_distributions.add(normalized_name)
        if normalized_name == "policy-check":
            saw_policy_check = True
            if (
                isinstance(verified_manifest.get("package"), dict)
                and distribution_version
                != verified_manifest["package"].get("version")
            ):
                raise BundleError(
                    "installed policy-check wheel version does not match manifest"
                )

        checked = 0
        for row in rows:
            if len(row) < 3:
                raise BundleError(
                    f"wheel RECORD is malformed: {distribution_name}"
                )
            name, encoded_digest, encoded_size = row[:3]
            if name == record_names[0]:
                continue
            relative = safe_relative_path(
                name,
                field=f"{distribution_name} RECORD path",
            )
            if not encoded_digest.startswith("sha256=") or not encoded_size.isdigit():
                raise BundleError(
                    f"wheel RECORD lacks SHA-256/size: {distribution_name}"
                )
            unresolved = installed_root / relative
            chain = [unresolved, *unresolved.parents]
            for candidate in chain:
                if candidate == installed_root:
                    break
                if candidate.is_symlink():
                    raise BundleError(
                        f"installed wheel path uses a symlink: "
                        f"{distribution_name}: {name}"
                    )
            installed_path = unresolved.resolve()
            try:
                installed_path.relative_to(installed_root)
            except ValueError as exc:
                raise BundleError(
                    f"installed file escapes selected environment: "
                    f"{distribution_name}"
                ) from exc
            if not installed_path.is_file():
                raise BundleError(
                    f"installed file is missing: {distribution_name}: {name}"
                )
            content = installed_path.read_bytes()
            if (
                normalized_name == "policy-check"
                and relative.as_posix() == DISTRIBUTION_IDENTITY_RECORD_PATH
            ):
                # The runtime manager overwrites this exact file at install
                # time with the bundle's own distribution identity (see
                # `manager._write_distribution_identity`), so its installed
                # bytes never match the wheel's built-in RECORD entry by
                # construction. Anchor its integrity to the digest-verified
                # manifest instead: `verified_manifest` is either produced
                # by `load_and_verify_bundle` in this same call, or was
                # handed in already verified by the caller, and — once
                # activated — is additionally pinned by the launcher's own
                # `EXPECTED_MANIFEST_SHA256` prelude. That anchor makes this
                # branch strictly narrower than the RECORD check it
                # replaces, not a relaxation of it: tampering with the
                # installed file is still caught (bytes must equal the
                # canonical serialization of the manifest's `distribution`
                # block), and tampering with the manifest itself is caught
                # by those independent digest checks.
                expected_identity = canonical_distribution_identity(
                    verified_manifest.get("distribution")
                ).encode("utf-8")
                if content != expected_identity:
                    raise BundleError(
                        "installed distribution identity does not match "
                        f"manifest: {distribution_name}: {name}"
                    )
            else:
                if len(content) != int(encoded_size):
                    raise BundleError(
                        f"installed file size changed: {distribution_name}: {name}"
                    )
                actual = base64.urlsafe_b64encode(
                    hashlib.sha256(content).digest()
                ).decode("ascii").rstrip("=")
                expected = encoded_digest[len("sha256="):].rstrip("=")
                if actual != expected:
                    raise BundleError(
                        f"installed file was modified: {distribution_name}: {name}"
                    )
            checked += 1
            recorded_paths.add(relative.as_posix())

            top_level = relative.parts[0]
            if top_level.endswith((".dist-info", ".data")):
                continue
            module_name = top_level.split(".", 1)[0]
            if module_name.isidentifier():
                executable_top_levels.add(module_name)
        if checked == 0:
            raise BundleError(
                f"wheel RECORD verified no installed files: {distribution_name}"
            )

    if not saw_policy_check:
        raise BundleError("installed wheels do not contain policy-check")
    forbidden_startup = list(installed_root.glob("*.pth"))
    for startup_module in ("sitecustomize", "usercustomize"):
        forbidden_startup.append(installed_root / startup_module)
        forbidden_startup.extend(
            installed_root.glob(f"{startup_module}.*")
        )
    if any(path.exists() or path.is_symlink() for path in forbidden_startup):
        raise BundleError(
            "installed environment contains unverified startup customization"
        )
    for module_name in sorted(executable_top_levels):
        shadow_candidates = [
            installed_root / f"{module_name}.py",
            installed_root / f"{module_name}.pyc",
        ]
        shadow_candidates.extend(installed_root.glob(f"{module_name}.*.so"))
        for shadow in shadow_candidates:
            if not (shadow.exists() or shadow.is_symlink()):
                continue
            relative = shadow.relative_to(installed_root).as_posix()
            if relative not in recorded_paths:
                raise BundleError(
                    f"installed environment shadows verified module: {module_name}"
                )
    return verified_manifest
