from __future__ import annotations

import os
import re
import sys
import tarfile
import tempfile
from pathlib import Path

from policy_check.identity import DistributionIdentity, IdentityError, identity

from .verification import (
    SHA256_RE,
    BundleError,
    load_and_verify_bundle,
    normalized_package_version,
    safe_relative_path,
    sha256_file,
    tree_sha256,
)


def _identity() -> DistributionIdentity:
    """Load distribution identity, normalizing failures to `BundleError`.

    `identity()` is fail-closed by design and raises `IdentityError` on a
    missing/unreadable/invalid `distribution.yml`. Callers in this module
    only translate `(OSError, tarfile.TarError)` into `BundleError`; left
    unguarded, a broken identity would surface as a raw `IdentityError`
    instead. Every call site here should go through this wrapper.
    """
    try:
        return identity()
    except IdentityError as exc:
        raise BundleError(f"distribution identity unavailable: {exc}") from exc


def _bundle_dir_re() -> re.Pattern[str]:
    return re.compile(
        r"^" + re.escape(_identity().distribution_name)
        + r"-v\d+\.\d+\.\d+(?:-fix\.\d+)?$"
    )


def write_checksums(root: Path) -> None:
    checksums = root / "SHA256SUMS"
    files = [
        path
        for path in root.rglob("*")
        if path.is_file() and path != checksums
    ]
    lines = [
        f"{sha256_file(path)}  {path.relative_to(root).as_posix()}"
        for path in sorted(files, key=lambda item: item.relative_to(root).as_posix())
    ]
    checksums.write_text("\n".join(lines) + "\n", encoding="utf-8")


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
            if _bundle_dir_re().fullmatch(root_name) is None:
                raise BundleError("archive bundle root name is invalid")
            target = destination / root_name
            if target.exists() or target.is_symlink():
                raise BundleError(f"archive destination already exists: {target}")
            with tempfile.TemporaryDirectory(
                prefix=".runtime-extract-",
                dir=destination,
            ) as temporary:
                stage = Path(temporary)
                if sys.version_info >= (3, 11, 4):
                    bundle_tar.extractall(stage, filter="data")
                else:
                    # Members were already restricted to safe relative
                    # regular-file or directory entries.
                    bundle_tar.extractall(stage)
                extracted = stage / root_name
                load_and_verify_bundle(
                    extracted, expected_repository=_identity().engine_repo
                )
                os.replace(extracted, target)
    except (OSError, tarfile.TarError) as exc:
        raise BundleError("bundle archive is unreadable or unsafe") from exc
    return target
