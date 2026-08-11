from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import uuid
import venv
from pathlib import Path
from typing import Any, Sequence


_ACTIVATION_STEPS = ("state", "current", "preflight", "lifecycle", "skill")
_ACTIVATION_JOURNAL = "activation.journal"
_ACTIVATION_ANCHOR = "activation.journal.anchor"
_ACTIVATION_SCHEMA_VERSION = 1


# The source package and the vendored bootstrap use one stdlib-only verifier.
# A copied manager loads its checksummed sibling explicitly because Python -I
# deliberately omits the script directory from sys.path.
try:
    from .verification import (
        VERSION_RE,
        BundleError as RuntimeBundleError,
        canonical_distribution_identity as _canonical_distribution_identity,
        load_and_verify_bundle as verify_bundle,
        normalized_package_version as _normalized_package_version,
        sha256_file as _sha256,
        verify_installed_wheel_payload as _verify_installed_wheels,
    )
except ImportError:
    _verifier_path = Path(__file__).with_name("runtime_verifier.py")
    _verifier_spec = importlib.util.spec_from_file_location(
        "_paulsha_runtime_verifier",
        _verifier_path,
    )
    if _verifier_spec is None or _verifier_spec.loader is None:
        raise RuntimeError("runtime verifier cannot be loaded")
    _verifier = importlib.util.module_from_spec(_verifier_spec)
    _verifier_spec.loader.exec_module(_verifier)
    VERSION_RE = _verifier.VERSION_RE
    RuntimeBundleError = _verifier.BundleError
    _canonical_distribution_identity = _verifier.canonical_distribution_identity
    verify_bundle = _verifier.load_and_verify_bundle
    _normalized_package_version = _verifier.normalized_package_version
    _sha256 = _verifier.sha256_file
    _verify_installed_wheels = _verifier.verify_installed_wheel_payload


# `policy_check.identity` is not vendored alongside this module (only
# verification.py travels into the bundle as runtime_verifier.py), so it is
# unavailable whenever this exact file runs standalone as runtime_manager.py
# under `python3 -I`/`-P` — which is every deployed `policy-preflight` and
# `policy-runtime-bundle` invocation (install/verify/exec/activate/rollback/
# uninstall), not just a one-off pre-install moment. `_expected_repository`
# falls back to `_VENDORED_EXPECTED_REPOSITORY` for that path; see its
# comment for why that does not weaken bundle authenticity the way reading
# the value back out of the bundle's own manifest would.
try:
    from policy_check.identity import identity as _identity
except ImportError:
    _identity = None


# Populated only in the *vendored copy* of this file (runtime/runtime_
# manager.py inside a built bundle): `builder.py`'s `_vendor_runtime_manager`
# rewrites this exact assignment to the distribution's `identity().
# engine_repo` at build time, before the file is copied into the bundle.
# It stays None in the source module (this file, imported normally as
# policy_check.runtime_bundle.manager), where `_identity` above resolves the
# value instead — so this constant is never itself read back from the
# bundle under verification: it lives in a *sibling* file whose own
# checksum is independently pinned by manifest["runtime"]["sha256"] and,
# once activated, by the deployed launcher script's own embedded checksum
# (see `_install_launcher`). A manifest that lies about its `repository`
# cannot rewrite this constant without also changing runtime_manager.py's
# checksum, which those independent anchors would then catch.
_VENDORED_EXPECTED_REPOSITORY: str | None = None


def _expected_repository() -> str:
    """The repository this manager requires every bundle manifest to match.

    Prefers the currently installed engine's distribution identity when
    `policy_check.identity` is importable (the source package, and any
    release venv once its own copy of policy-check is on sys.path). When it
    is not — the normal case for the vendored, `-I`/`-P`-executed
    runtime_manager.py — this falls back to the build-time constant baked in
    by `builder.py`. It deliberately never reads the expected value out of
    the bundle's own manifest.json: that would compare the manifest's
    declared `repository` field against itself and accept anything.
    """
    if _identity is not None:
        return _identity().engine_repo
    if _VENDORED_EXPECTED_REPOSITORY:
        return _VENDORED_EXPECTED_REPOSITORY
    raise RuntimeBundleError(
        "distribution identity is unavailable: policy_check.identity could "
        "not be imported and this runtime manager was not vendored with a "
        "build-time repository constant"
    )


def _safe_distribution_name(value: Any, *, source: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeBundleError(
            f"{source} distribution identity is missing: distribution_name"
        )
    name = value.strip()
    if name in {".", ".."} or "/" in name or "\\" in name:
        raise RuntimeBundleError(
            f"{source} distribution_name is not a single safe path component"
        )
    return name


def _manifest_distribution_name(manifest: dict[str, Any]) -> str:
    distribution = manifest.get("distribution")
    _canonical_distribution_identity(distribution)
    if not isinstance(distribution, dict):
        raise RuntimeBundleError("bundle manifest is missing distribution identity")
    return _safe_distribution_name(
        distribution.get("distribution_name"),
        source="bundle manifest",
    )


def _distribution_name(manifest: dict[str, Any] | None = None) -> str:
    if manifest is not None:
        return _manifest_distribution_name(manifest)
    if _identity is None:
        raise RuntimeBundleError(
            "distribution identity is unavailable: cannot derive the runtime root"
        )
    try:
        distribution_name = _identity().distribution_name
    except (AttributeError, RuntimeError) as exc:
        raise RuntimeBundleError(
            "distribution identity is unavailable: cannot derive the runtime root"
        ) from exc
    return _safe_distribution_name(distribution_name, source="installed")


def _default_root(manifest: dict[str, Any] | None = None) -> Path:
    configured = os.environ.get("PSC_CONVENTIONS_ROOT")
    if configured:
        return Path(configured).expanduser()
    distribution_name = _distribution_name(manifest)
    data_home = os.environ.get("XDG_DATA_HOME")
    if data_home:
        return Path(data_home).expanduser() / distribution_name
    return Path.home() / ".local" / "share" / distribution_name


def _default_skill_target() -> Path:
    return Path.home() / ".agents" / "skills" / "preflight-ci"


def _venv_python(root: Path) -> Path:
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _venv_site_packages(root: Path) -> Path:
    if os.name == "nt":
        return root / "Lib" / "site-packages"
    return (
        root
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )


def _write_distribution_identity(venv_root: Path, manifest: dict[str, Any]) -> None:
    """Write the bundle's own distribution identity into the venv this
    install just created (`staging / "venv"`), so the freshly installed
    release's `policy_check.identity` reports the identity that governs it
    instead of whatever the wheel happened to ship as its built-in default.

    Resolves the target through `venv_root` — the exact venv this call
    built — never through a bare `python3` looked up on PATH or
    `importlib.util.find_spec` run from the invoking interpreter. The
    invoking interpreter is not the installed release: it could be a
    system `python3`, or (in a dev/editable checkout) one that already
    happens to import an unrelated `policy_check.data`, which would make
    this silently overwrite the wrong package's data file instead of the
    one this install produced.

    Fail-closed: a manifest missing `distribution` (or missing any of its
    required fields), or a target site-packages tree that does not
    actually contain an installed `policy_check.data` package, aborts the
    install instead of silently keeping the wheel's built-in identity.

    Serializes through `verification.canonical_distribution_identity` —
    the same single source of truth `verify_installed_wheel_payload` reads
    back at attestation time — so the write here and the check there can
    never drift apart.
    """
    content = _canonical_distribution_identity(manifest.get("distribution"))
    target_dir = _venv_site_packages(venv_root) / "policy_check" / "data"
    if not target_dir.is_dir():
        raise RuntimeBundleError("installed policy_check.data package not found")
    target = target_dir / "distribution.yml"
    target.write_text(content, encoding="utf-8")


def _isolated_subprocess_env() -> dict[str, str]:
    return {
        **{
            key: value
            for key, value in os.environ.items()
            if key not in {"PYTHONPATH", "PYTHONHOME"}
        },
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


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
        raise RuntimeBundleError(f"command unavailable: {argv[0]}") from exc
    if result.returncode != 0:
        details: list[str] = []
        for line in (result.stderr or result.stdout).strip().splitlines():
            if not line.strip():
                continue
            details.append(
                line
                if len(line) <= 500
                else f"{line[:240]} ... {line[-240:]}"
            )
        diagnostic = "\n".join(details[-12:])
        if len(diagnostic) > 3000:
            diagnostic = diagnostic[-3000:]
        suffix = f":\n{diagnostic}" if diagnostic else ""
        raise RuntimeBundleError(
            f"command failed ({result.returncode}): {argv[0]}{suffix}"
        )
    return result.stdout.strip()


def _atomic_write_bytes(
    path: Path,
    content: bytes,
    *,
    mode: int | None = None,
    temp_prefix: str = "tmp",
) -> None:
    """Publish ``content`` at ``path`` with a power-loss-safe replace.

    The temporary file's content is flushed and fsync'd to disk *before* the
    rename that publishes it, so a crash between rename and content flush can
    never leave the published file empty or truncated. The containing
    directory is fsync'd afterwards so the rename itself is durable too. On
    any failure the temporary file is always removed; nothing is ever left
    behind for a caller to trip over.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{temp_prefix}-{uuid.uuid4().hex}")
    try:
        with temporary.open("wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if mode is not None:
            temporary.chmod(mode)
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    content = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    _atomic_write_bytes(path, content)


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_bytes_atomic(path: Path, content: bytes, *, mode: int = 0o600) -> None:
    _atomic_write_bytes(path, content, mode=mode)


def _canonical_json(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _journal_paths(runtime_root: Path) -> tuple[Path, Path]:
    return (
        runtime_root / _ACTIVATION_JOURNAL,
        runtime_root / _ACTIVATION_ANCHOR,
    )


def _encode_regular_snapshot(
    snapshot: tuple[bytes, int] | None,
) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    content, mode = snapshot
    return {
        "content": base64.b64encode(content).decode("ascii"),
        "mode": mode,
    }


def _decode_regular_snapshot(value: Any) -> tuple[bytes, int] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise RuntimeBundleError("activation journal snapshot is invalid")
    content = value.get("content")
    mode = value.get("mode")
    if not isinstance(content, str) or not isinstance(mode, int) or not 0 <= mode <= 0o777:
        raise RuntimeBundleError("activation journal snapshot is invalid")
    try:
        decoded = base64.b64decode(content.encode("ascii"), validate=True)
    except (ValueError, UnicodeError) as exc:
        raise RuntimeBundleError("activation journal snapshot is invalid") from exc
    return decoded, mode


def _activation_snapshot(
    runtime_root: Path,
    skill_target: Path,
) -> dict[str, Any]:
    return {
        "state": _encode_regular_snapshot(
            _snapshot_regular_file(runtime_root / "state.json")
        ),
        "current": _snapshot_symlink(runtime_root / "current"),
        "preflight": _encode_regular_snapshot(
            _snapshot_regular_file(runtime_root / "bin" / "policy-preflight")
        ),
        "lifecycle": _encode_regular_snapshot(
            _snapshot_regular_file(runtime_root / "bin" / "policy-runtime-bundle")
        ),
        "skill": _snapshot_symlink(skill_target),
    }


def _activation_event(
    sequence: int,
    previous_digest: str | None,
    event: str,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    unsigned = {
        "schema_version": _ACTIVATION_SCHEMA_VERSION,
        "sequence": sequence,
        "previous_digest": previous_digest or ("0" * 64),
        "event": event,
        "payload": payload,
    }
    digest = hashlib.sha256(_canonical_json(unsigned)).hexdigest()
    return {**unsigned, "digest": digest}, digest


def _validate_journal_path(path: Path, label: str) -> None:
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise RuntimeBundleError(f"activation journal {label} is not a regular file")


def _append_activation_event(
    journal_path: Path,
    anchor_path: Path,
    *,
    sequence: int,
    previous_digest: str | None,
    event: str,
    payload: dict[str, Any],
) -> tuple[int, str]:
    record, digest = _activation_event(sequence, previous_digest, event, payload)
    _validate_journal_path(journal_path, "file")
    _validate_journal_path(anchor_path, "anchor")
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    with journal_path.open("ab") as stream:
        stream.write(_canonical_json(record) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    _fsync_directory(journal_path.parent)
    _write_bytes_atomic(anchor_path, f"{digest}\n".encode("ascii"))
    return sequence + 1, digest


def _read_activation_records(runtime_root: Path) -> list[dict[str, Any]] | None:
    journal_path, anchor_path = _journal_paths(runtime_root)
    _validate_journal_path(journal_path, "file")
    _validate_journal_path(anchor_path, "anchor")
    if not journal_path.exists():
        if anchor_path.exists():
            anchor_path.unlink()
            _fsync_directory(runtime_root)
        return None
    if not anchor_path.is_file():
        raise RuntimeBundleError("activation journal anchor is missing")
    try:
        anchor = anchor_path.read_text(encoding="ascii").strip()
        raw = journal_path.read_bytes()
    except (OSError, UnicodeError) as exc:
        raise RuntimeBundleError("activation journal cannot be read") from exc
    if re.fullmatch(r"[0-9a-f]{64}", anchor) is None:
        raise RuntimeBundleError("activation journal anchor is invalid")

    records: list[dict[str, Any]] = []
    previous_digest = "0" * 64
    expected_sequence = 1
    anchor_index: int | None = None
    lines = raw.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if not line.endswith(b"\n"):
            if anchor_index is None:
                raise RuntimeBundleError("activation journal has an uncommitted partial record")
            break
        try:
            record = json.loads(line.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            if anchor_index is not None:
                raise RuntimeBundleError("activation journal has a tampered record") from exc
            raise RuntimeBundleError("activation journal is invalid") from exc
        if not isinstance(record, dict):
            raise RuntimeBundleError("activation journal record is invalid")
        digest = record.get("digest")
        if (
            record.get("schema_version") != _ACTIVATION_SCHEMA_VERSION
            or record.get("sequence") != expected_sequence
            or record.get("previous_digest") != previous_digest
            or not isinstance(record.get("event"), str)
            or not isinstance(record.get("payload"), dict)
            or not isinstance(digest, str)
        ):
            raise RuntimeBundleError("activation journal record is invalid")
        unsigned = dict(record)
        del unsigned["digest"]
        calculated = hashlib.sha256(_canonical_json(unsigned)).hexdigest()
        if digest != calculated:
            raise RuntimeBundleError("activation journal digest mismatch")
        records.append(record)
        previous_digest = digest
        expected_sequence += 1
        if digest == anchor:
            anchor_index = index
    if anchor_index is None:
        raise RuntimeBundleError("activation journal anchor does not match journal")
    trusted = records[: anchor_index + 1]
    if not trusted or trusted[0].get("event") != "begin":
        raise RuntimeBundleError("activation journal does not begin with activation")
    return trusted


def _clear_activation_journal(runtime_root: Path) -> None:
    journal_path, anchor_path = _journal_paths(runtime_root)
    journal_path.unlink(missing_ok=True)
    _fsync_directory(runtime_root)
    anchor_path.unlink(missing_ok=True)
    _fsync_directory(runtime_root)


def _load_state(path: Path, *, required: bool = False) -> dict[str, Any]:
    if not path.is_file():
        if required:
            raise RuntimeBundleError("install state is missing")
        return {}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeBundleError("install state is invalid") from exc
    if not isinstance(state, dict):
        raise RuntimeBundleError("install state must be a JSON object")
    return state


def _atomic_symlink(target: Path, link: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    temporary = link.with_name(f".{link.name}.tmp-{uuid.uuid4().hex}")
    temporary.symlink_to(target)
    os.replace(temporary, link)
    _fsync_directory(link.parent)


def _snapshot_regular_file(path: Path) -> tuple[bytes, int] | None:
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise RuntimeBundleError(f"managed path is not a regular file: {path}")
    if not path.exists():
        return None
    return path.read_bytes(), path.stat().st_mode & 0o777


def _restore_regular_file(
    path: Path,
    snapshot: tuple[bytes, int] | None,
) -> None:
    if snapshot is None:
        path.unlink(missing_ok=True)
        return
    content, mode = snapshot
    _atomic_write_bytes(path, content, mode=mode, temp_prefix="restore")


def _snapshot_symlink(path: Path) -> str | None:
    if path.is_symlink():
        return os.readlink(path)
    if path.exists():
        raise RuntimeBundleError(f"managed path is not a symlink: {path}")
    return None


def _restore_symlink(path: Path, target: str | None) -> None:
    if target is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.restore-{uuid.uuid4().hex}")
    temporary.symlink_to(target)
    os.replace(temporary, path)
    _fsync_directory(path.parent)


def _ensure_skill_target(target: Path, root: Path) -> None:
    if target.exists() and not target.is_symlink():
        raise RuntimeBundleError(f"refusing to overwrite unmanaged skill target: {target}")
    if target.is_symlink():
        try:
            target.resolve(strict=False).relative_to(root.resolve())
        except ValueError as exc:
            raise RuntimeBundleError(
                f"refusing to replace skill symlink outside runtime root: {target}"
            ) from exc


def _require_venv_support(cwd: Path) -> None:
    try:
        _run(
            [sys.executable, "-I", "-m", "ensurepip", "--version"],
            cwd=cwd,
        )
    except RuntimeBundleError as exc:
        raise RuntimeBundleError(
            "Python venv/ensurepip support is unavailable; install python3-venv"
        ) from exc


def _require_runtime_commands(manifest: dict[str, Any], cwd: Path) -> None:
    checks = {
        "git": ("git", ["--version"]),
        "sha256sum": ("sha256sum", ["--version"]),
        "universal-ctags": ("ctags", ["--output-format=json", "--version"]),
    }
    declared = manifest["prerequisites"]
    for prerequisite in declared:
        check = checks.get(prerequisite)
        if check is None:
            continue
        command, arguments = check
        if shutil.which(command) is None:
            raise RuntimeBundleError(
                "runtime install prerequisite unavailable: "
                f"{prerequisite} ({command})"
            )
        try:
            _run([command, *arguments], cwd=cwd)
        except RuntimeBundleError as exc:
            raise RuntimeBundleError(
                "runtime install prerequisite is incompatible: "
                f"{prerequisite} ({command})"
            ) from exc


def _symlink_points_to(link: Path, target: Path) -> bool:
    return (
        link.is_symlink()
        and link.resolve(strict=False) == target.resolve(strict=False)
    )


def _cleanup_displaced_release(displaced: Path) -> None:
    try:
        shutil.rmtree(displaced)
    except OSError as exc:
        print(
            "WARNING: replacement succeeded but old release cleanup failed: "
            f"{displaced} ({exc.__class__.__name__})",
            file=sys.stderr,
        )


def _make_smoke_repo(root: Path, version: str) -> tuple[Path, Path]:
    repo = root / "fixture"
    repo.mkdir()
    config = (
        "policy_profile: flat\n"
        f"policy_version: {version}\n"
        "tier: shareable\n"
        "agent_files:\n"
        "  mode: copy\n"
        "conventions_engine:\n"
        "  mode: pip\n"
        "preflight:\n"
        "  steps:\n"
        "    - name: runtime-smoke\n"
        "      kind: validation\n"
        f"      argv: [\"{sys.executable}\", \"-c\", \"print('runtime bundle smoke')\"]\n"
    )
    (repo / ".project-policy.yml").write_text(config, encoding="utf-8")
    (repo / "README.md").write_text(
        "# Runtime Bundle Fixture\n\n"
        "This isolated repository validates a deployed bundle without a source checkout. "
        "The text is intentionally long enough for the README policy.\n\n"
        "## Install\n\nInstalled by the runtime manager.\n\n"
        "## Usage\n\nRun policy-preflight through the stable selector.\n\n"
        f"## Version\n\n{version}\n",
        encoding="utf-8",
    )
    (repo / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [Unreleased]\n\n### Added\n- Runtime smoke fixture.\n",
        encoding="utf-8",
    )
    (repo / "VERSION").write_text(f"{version}\n", encoding="utf-8")
    canonical = repo / "CLAUDE.md"
    canonical.write_text(
        f"policy_version: {version}\n\n# Runtime smoke agent policy\n",
        encoding="utf-8",
    )
    (repo / "AGENTS.md").write_text(canonical.read_text(encoding="utf-8"), encoding="utf-8")
    (repo / "GEMINI.md").write_text(canonical.read_text(encoding="utf-8"), encoding="utf-8")
    copilot = repo / ".github" / "copilot-instructions.md"
    copilot.parent.mkdir()
    copilot.write_text(canonical.read_text(encoding="utf-8"), encoding="utf-8")
    body = repo / "pr-body.md"
    body.write_text("Runtime bundle artifact smoke.\n", encoding="utf-8")
    git_env = dict(os.environ)
    git_env["GIT_CONFIG_GLOBAL"] = os.devnull
    git_env["GIT_CONFIG_SYSTEM"] = os.devnull
    git_env["GIT_CONFIG_NOSYSTEM"] = "1"
    git_env["HOME"] = str(root)
    _run(["git", "init", "-q", "-b", "main"], cwd=repo, env=git_env)
    _run(
        ["git", "config", "user.email", "runtime@example.invalid"],
        cwd=repo,
        env=git_env,
    )
    _run(["git", "config", "user.name", "Runtime Bundle"], cwd=repo, env=git_env)
    _run(["git", "add", "."], cwd=repo, env=git_env)
    _run(
        ["git", "commit", "-qm", "chore: runtime smoke baseline"],
        cwd=repo,
        env=git_env,
    )
    _run(
        ["git", "tag", "-a", f"v{version}", "-m", f"v{version}"],
        cwd=repo,
        env=git_env,
    )
    _run(
        ["git", "update-ref", "refs/remotes/origin/main", "HEAD"],
        cwd=repo,
        env=git_env,
    )
    _run(
        ["git", "switch", "-qc", "feature/runtime-smoke"],
        cwd=repo,
        env=git_env,
    )
    return repo, body


def _smoke(staging: Path, manifest: dict[str, Any]) -> None:
    version = manifest["policy_version"]
    python = _venv_python(staging / "venv")
    with tempfile.TemporaryDirectory(prefix="runtime-smoke-") as temporary:
        home = Path(temporary) / "home"
        home.mkdir()
        repo, body = _make_smoke_repo(Path(temporary), version)
        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(home),
            "LC_ALL": "C",
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        _run(
            [
                str(python),
                "-I",
                "-m",
                "policy_check.preflight",
                "--repo",
                str(repo),
                "--installed-manifest",
                str(staging / "artifact" / "manifest.json"),
                "--offline",
                "--pr-title",
                "chore: verify runtime bundle",
                "--pr-body-file",
                str(body),
                "--base",
                "main",
                "--head",
                "feature/runtime-smoke",
                "--repo-visibility",
                "private",
            ],
            cwd=repo,
            env=env,
        )


def _attest_installed_release(release: Path) -> None:
    _verify_installed_wheels(
        release / "artifact",
        _venv_site_packages(release / "venv"),
        expected_repository=_expected_repository(),
    )


def _install_launcher(
    root: Path,
    release: Path,
    *,
    only: str | None = None,
) -> None:
    expected_manifest_sha256 = _sha256(
        release / "artifact" / "manifest.json"
    )
    if re.fullmatch(r"[0-9a-f]{64}", expected_manifest_sha256) is None:
        raise RuntimeBundleError("active manifest digest is invalid")
    trust_prelude = (
        f'EXPECTED_MANIFEST_SHA256="{expected_manifest_sha256}"\n'
        'ACTIVE_MANIFEST="$RUNTIME_ROOT/current/artifact/manifest.json"\n'
        '[[ -f "$ACTIVE_MANIFEST" ]] || { '
        'echo "ERROR: active runtime manifest is missing" >&2; exit 2; }\n'
        'ACTUAL_MANIFEST_SHA256="$("$PYTHON_BIN" -I -B -c '
        '\'import hashlib, sys; print(hashlib.sha256('
        'open(sys.argv[1], "rb").read()).hexdigest())\' "$ACTIVE_MANIFEST")"\n'
        '[[ "$ACTUAL_MANIFEST_SHA256" == "$EXPECTED_MANIFEST_SHA256" ]] || { '
        'echo "ERROR: active runtime manifest does not match launcher anchor" >&2; '
        'exit 2; }\n'
        'MANAGER_SHA256="$("$PYTHON_BIN" -I -B -c '
        '\'import json, re, sys; data=json.load(open(sys.argv[1], encoding="utf-8")); '
        'runtime=data.get("runtime"); '
        'ok=isinstance(runtime, dict) and '
        'runtime.get("path") == "runtime/runtime_manager.py" and '
        're.fullmatch(r"[0-9a-f]{64}", str(runtime.get("sha256") or "")); '
        'sys.exit(2) if not ok else print(runtime["sha256"])\' '
        '"$ACTIVE_MANIFEST")" || { '
        'echo "ERROR: active runtime manifest identity is invalid" >&2; exit 2; }\n'
        'printf "%s  %s\\n" "$MANAGER_SHA256" "$MANAGER" | '
        'sha256sum --check --strict - >/dev/null || { '
        'echo "ERROR: active runtime manager checksum mismatch" >&2; exit 2; }\n'
    )
    launcher = root / "bin" / "policy-preflight"
    launcher.parent.mkdir(parents=True, exist_ok=True)
    preflight_text = (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'RUNTIME_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"\n'
        'TARGET_REPO="$PWD"\n'
        'if [[ "${1:-}" == "--repo" ]]; then\n'
        '  [[ $# -ge 2 ]] || { echo "ERROR: --repo requires a value" >&2; exit 2; }\n'
        '  TARGET_REPO="$2"\n'
        '  shift 2\n'
        'elif [[ "${1:-}" == --repo=* ]]; then\n'
        '  TARGET_REPO="${1#--repo=}"\n'
        '  shift\n'
        "fi\n"
        'MANAGER="$RUNTIME_ROOT/current/artifact/runtime/runtime_manager.py"\n'
        '[[ -f "$MANAGER" ]] || { echo "ERROR: no active runtime manager" >&2; exit 2; }\n'
        'PYTHON_BIN="${PYTHON_BIN:-python3}"\n'
        'command -v "$PYTHON_BIN" >/dev/null 2>&1 || { '
        'echo "ERROR: Python 3.11+ is required by the runtime bundle" >&2; exit 2; }\n'
        '"$PYTHON_BIN" -I -c \'import sys; raise SystemExit(0 if '
        'sys.version_info >= (3, 11) else 1)\' || { '
        'echo "ERROR: Python 3.11+ is required by the runtime bundle" >&2; exit 2; }\n'
        + trust_prelude
        + 'exec "$PYTHON_BIN" -I -B "$MANAGER" exec --root "$RUNTIME_ROOT" '
        '--repo "$TARGET_REPO" -- "$@"\n'
    )
    lifecycle = root / "bin" / "policy-runtime-bundle"
    lifecycle_text = (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'RUNTIME_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"\n'
        'COMMAND="${1:-}"\n'
        '[[ -n "$COMMAND" ]] || { '
        'echo "ERROR: expected install, activate, rollback, recover, or uninstall" >&2; exit 2; }\n'
        "shift\n"
        'case "$COMMAND" in\n'
        '  install|activate|rollback|uninstall|recover) ;;\n'
        '  *) echo "ERROR: unsupported deployed lifecycle command: $COMMAND" >&2; exit 2 ;;\n'
        "esac\n"
        'MANAGER="$RUNTIME_ROOT/current/artifact/runtime/runtime_manager.py"\n'
        '[[ -f "$MANAGER" ]] || { echo "ERROR: no active runtime manager" >&2; exit 2; }\n'
        'PYTHON_BIN="${PYTHON_BIN:-python3}"\n'
        'command -v "$PYTHON_BIN" >/dev/null 2>&1 || { '
        'echo "ERROR: Python 3.11+ is required by the runtime bundle" >&2; exit 2; }\n'
        '"$PYTHON_BIN" -I -c \'import sys; raise SystemExit(0 if '
        'sys.version_info >= (3, 11) else 1)\' || { '
        'echo "ERROR: Python 3.11+ is required by the runtime bundle" >&2; exit 2; }\n'
        + trust_prelude
        + 'exec "$PYTHON_BIN" -I -B "$MANAGER" "$COMMAND" --root "$RUNTIME_ROOT" "$@"\n'
    )
    launchers = {
        "preflight": (launcher, preflight_text),
        "lifecycle": (lifecycle, lifecycle_text),
    }
    if only is not None and only not in launchers:
        raise RuntimeBundleError(f"unknown launcher activation step: {only}")
    selected = (
        launchers.items()
        if only is None
        else ((only, launchers[only]),)
    )
    for _name, (destination, text) in selected:
        _atomic_write_bytes(destination, text.encode("utf-8"), mode=0o755)


def _restore_activation_snapshot(
    runtime_root: Path,
    skill_target: Path,
    snapshots: dict[str, Any],
) -> None:
    _restore_symlink(skill_target, snapshots["skill"])
    _restore_regular_file(
        runtime_root / "bin" / "policy-runtime-bundle",
        _decode_regular_snapshot(snapshots["lifecycle"]),
    )
    _restore_regular_file(
        runtime_root / "bin" / "policy-preflight",
        _decode_regular_snapshot(snapshots["preflight"]),
    )
    _restore_symlink(runtime_root / "current", snapshots["current"])
    _restore_regular_file(
        runtime_root / "state.json",
        _decode_regular_snapshot(snapshots["state"]),
    )


def recover(root: Path, skill_target: Path | None = None) -> bool:
    runtime_root = root.resolve()
    records = _read_activation_records(runtime_root)
    if records is None:
        return False
    begin = records[0]["payload"]
    recorded_root = begin.get("runtime_root")
    recorded_skill_target = begin.get("skill_target")
    snapshots = begin.get("snapshots")
    if (
        recorded_root != str(runtime_root)
        or not isinstance(recorded_skill_target, str)
        or begin.get("steps") != list(_ACTIVATION_STEPS)
        or not isinstance(begin.get("release"), str)
        or not isinstance(snapshots, dict)
        or set(snapshots) != set(_ACTIVATION_STEPS)
    ):
        raise RuntimeBundleError("activation journal ownership is invalid")
    journal_skill_target = Path(recorded_skill_target)

    terminal = records[-1]["event"]
    if terminal in {"commit", "aborted", "recovered"}:
        # A finished journal (committed, aborted, or already recovered) only
        # ever deletes its own journal/anchor files under the trusted,
        # caller-resolved runtime_root; it never writes to skill_target. The
        # journal's recorded skill_target is therefore inert here, so this
        # cleanup-only path is safe to take even when the caller (e.g.
        # uninstall()) has no opinion on skill_target.
        if terminal == "commit":
            completed = {
                record["payload"].get("step")
                for record in records
                if record["event"] == "complete"
            }
            if completed != set(_ACTIVATION_STEPS):
                raise RuntimeBundleError("activation journal commit is incomplete")
        _clear_activation_journal(runtime_root)
        return True

    # An interrupted activation restores the previous generation by writing
    # to journal_skill_target (via _restore_activation_snapshot). The journal
    # is a user-writable file: an attacker able to write it can rebuild a
    # fully self-consistent hash chain around any skill_target of their
    # choosing. Trusting that recorded value when the caller left
    # skill_target unspecified would let a forged journal alone decide which
    # writable path automatic recovery overwrites. So even the "unspecified"
    # case is pinned to a concrete, caller-independent expectation (the
    # conventional default) and verified against the journal *before* any
    # restore write happens — fail closed on any mismatch, never let the
    # journal decide on its own.
    expected_skill_target = (
        skill_target if skill_target is not None else _default_skill_target()
    )
    if expected_skill_target.absolute() != journal_skill_target.absolute():
        raise RuntimeBundleError(
            "activation journal skill target does not match the trusted "
            "recovery target; refusing to let the journal alone decide "
            "which path to overwrite"
        )

    for record in records[1:]:
        if record["event"] not in {"prepare", "complete"}:
            raise RuntimeBundleError("activation journal event is invalid")
        step = record["payload"].get("step")
        if step not in _ACTIVATION_STEPS:
            raise RuntimeBundleError("activation journal step is invalid")
    try:
        _restore_activation_snapshot(runtime_root, journal_skill_target, snapshots)
    except (OSError, RuntimeBundleError) as exc:
        raise RuntimeBundleError(
            "activation recovery could not restore the previous generation"
        ) from exc
    next_sequence = records[-1]["sequence"] + 1
    _, digest = _append_activation_event(
        *_journal_paths(runtime_root),
        sequence=next_sequence,
        previous_digest=records[-1]["digest"],
        event="recovered",
        payload={},
    )
    del digest
    _clear_activation_journal(runtime_root)
    return True


def _switch_active_release(
    runtime_root: Path,
    skill_target: Path,
    release: Path,
    state: dict[str, Any],
) -> None:
    runtime_root.mkdir(parents=True, exist_ok=True)
    snapshots = _activation_snapshot(runtime_root, skill_target)
    journal_path, anchor_path = _journal_paths(runtime_root)
    next_sequence, previous_digest = _append_activation_event(
        journal_path,
        anchor_path,
        sequence=1,
        previous_digest=None,
        event="begin",
        payload={
            "runtime_root": str(runtime_root),
            "skill_target": str(skill_target.absolute()),
            "release": str(release.resolve()),
            "steps": list(_ACTIVATION_STEPS),
            "snapshots": snapshots,
        },
    )
    try:
        mutations = (
            ("state", lambda: _write_json_atomic(runtime_root / "state.json", state)),
            ("current", lambda: _atomic_symlink(release, runtime_root / "current")),
            (
                "preflight",
                lambda: _install_launcher(runtime_root, release, only="preflight"),
            ),
            (
                "lifecycle",
                lambda: _install_launcher(runtime_root, release, only="lifecycle"),
            ),
            (
                "skill",
                lambda: _atomic_symlink(
                    release / "artifact" / "skills" / "preflight-ci",
                    skill_target,
                ),
            ),
        )
        for step, mutate in mutations:
            next_sequence, previous_digest = _append_activation_event(
                journal_path,
                anchor_path,
                sequence=next_sequence,
                previous_digest=previous_digest,
                event="prepare",
                payload={"step": step},
            )
            mutate()
            next_sequence, previous_digest = _append_activation_event(
                journal_path,
                anchor_path,
                sequence=next_sequence,
                previous_digest=previous_digest,
                event="complete",
                payload={"step": step},
            )
        _append_activation_event(
            journal_path,
            anchor_path,
            sequence=next_sequence,
            previous_digest=previous_digest,
            event="commit",
            payload={},
        )
    except BaseException as exc:
        failures: list[str] = []
        try:
            _restore_activation_snapshot(runtime_root, skill_target, snapshots)
        except (OSError, RuntimeBundleError) as restore_exc:
            failures.append(f"managed state ({restore_exc.__class__.__name__})")
        if failures:
            raise RuntimeBundleError(
                "activation failed and managed state rollback was incomplete: "
                + ", ".join(failures)
            ) from exc
        next_sequence, previous_digest = _append_activation_event(
            journal_path,
            anchor_path,
            sequence=next_sequence,
            previous_digest=previous_digest,
            event="aborted",
            payload={},
        )
        del next_sequence, previous_digest
        _clear_activation_journal(runtime_root)
        raise


def install(
    bundle: Path,
    root: Path | None,
    skill_target: Path,
    *,
    force_reinstall: bool = False,
) -> str:
    manifest = verify_bundle(bundle, expected_repository=_expected_repository())
    _manifest_distribution_name(manifest)
    compatibility = manifest["runtime_compatibility"]
    current = {
        "implementation": sys.implementation.name,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "abi": str(sysconfig.get_config_var("SOABI") or ""),
        "platform": sysconfig.get_platform(),
    }
    if compatibility != current:
        raise RuntimeBundleError(
            "bundle runtime is incompatible: "
            f"need {compatibility}, current {current}"
        )
    version = manifest["policy_version"]
    runtime_root = (
        root if root is not None else _default_root(manifest)
    ).resolve()
    recover(runtime_root, skill_target)
    releases = runtime_root / "releases"
    destination = releases / version
    _ensure_skill_target(skill_target, runtime_root)
    state_path = runtime_root / "state.json"
    state = _load_state(state_path)
    destination_exists = destination.exists() or destination.is_symlink()
    if destination_exists and not force_reinstall:
        raise RuntimeBundleError(f"release already installed: {version}")
    if force_reinstall:
        installed = state.get("installed")
        if (
            not destination_exists
            or destination.is_symlink()
            or not destination.is_dir()
            or not isinstance(installed, list)
            or version not in installed
            or not all(isinstance(item, str) for item in installed)
        ):
            raise RuntimeBundleError(
                "force-reinstall requires a state-owned release directory"
            )
        try:
            destination.resolve().relative_to(releases.resolve())
        except ValueError as exc:
            raise RuntimeBundleError(
                "force-reinstall release escapes runtime root"
            ) from exc
    current_version = (
        state.get("current") if isinstance(state.get("current"), str) else None
    )
    previous = (
        state.get("previous")
        if current_version == version
        else current_version
    )
    if not isinstance(previous, str):
        previous = None
    _require_venv_support(bundle)
    _require_runtime_commands(manifest, bundle)
    releases.mkdir(parents=True, exist_ok=True)
    staging = releases / f".staging-{version}-{uuid.uuid4().hex}"
    displaced: Path | None = None
    try:
        (staging / "artifact").parent.mkdir(parents=True)
        shutil.copytree(bundle.resolve(), staging / "artifact")
        verify_bundle(
            staging / "artifact",
            expected_repository=_expected_repository(),
        )
        try:
            venv.EnvBuilder(with_pip=True, clear=False).create(staging / "venv")
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeBundleError(
                "cannot create a venv with pip; install python3-venv"
            ) from exc
        python = _venv_python(staging / "venv")
        wheel_dir = staging / "artifact" / "wheels"
        package_version = manifest["package"]["version"]
        _run(
            [
                str(python),
                "-I",
                "-B",
                "-m",
                "pip",
                "install",
                "--no-index",
                "--find-links",
                str(wheel_dir),
                f"policy-check=={package_version}",
            ],
            cwd=staging,
            env=_isolated_subprocess_env(),
        )
        _write_distribution_identity(staging / "venv", manifest)
        _run(
            [
                str(python),
                "-I",
                "-B",
                "-m",
                "pip",
                "uninstall",
                "--yes",
                "pip",
                "setuptools",
            ],
            cwd=staging,
            env=_isolated_subprocess_env(),
        )
        _attest_installed_release(staging)
        _smoke(staging, manifest)
        _write_json_atomic(
            staging / "VERIFIED",
            {
                "schema_version": 1,
                "policy_version": version,
                "manifest_sha256": _sha256(staging / "artifact" / "manifest.json"),
                "python_sha256": _sha256(python.resolve()),
                "pyvenv_cfg_sha256": _sha256(
                    staging / "venv" / "pyvenv.cfg"
                ),
            },
        )
        if force_reinstall:
            displaced = releases / f".replaced-{version}-{uuid.uuid4().hex}"
            os.replace(destination, displaced)
            try:
                os.replace(staging, destination)
            except BaseException:
                os.replace(displaced, destination)
                displaced = None
                raise
        else:
            os.replace(staging, destination)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        if displaced is not None and displaced.exists() and not destination.exists():
            os.replace(displaced, destination)
        raise

    new_state = {
        "schema_version": 1,
        "current": version,
        "previous": previous,
        "installed": sorted(
            path.name
            for path in releases.iterdir()
            if path.is_dir() and not path.name.startswith(".")
        ),
    }
    try:
        _switch_active_release(
            runtime_root,
            skill_target,
            destination,
            new_state,
        )
    except BaseException:
        failed = releases / f".failed-{version}-{uuid.uuid4().hex}"
        if destination.exists():
            os.replace(destination, failed)
        if displaced is not None and displaced.exists():
            try:
                os.replace(displaced, destination)
            except BaseException:
                if failed.exists() and not destination.exists():
                    os.replace(failed, destination)
                raise
            displaced = None
        if failed.exists():
            try:
                shutil.rmtree(failed)
            except OSError as exc:
                print(
                    "WARNING: activation failed and staged release cleanup failed: "
                    f"{failed} ({exc.__class__.__name__})",
                    file=sys.stderr,
                )
        raise
    if displaced is not None:
        _cleanup_displaced_release(displaced)
    return version


def _verified_release(root: Path, version: str) -> Path:
    if VERSION_RE.fullmatch(version) is None:
        raise RuntimeBundleError("invalid release version")
    releases = root.resolve() / "releases"
    release_path = releases / version
    if release_path.is_symlink():
        raise RuntimeBundleError("installed release must not be a symlink")
    release = release_path.resolve()
    try:
        release.relative_to(releases.resolve())
    except ValueError as exc:
        raise RuntimeBundleError("installed release escapes runtime root") from exc
    verified = release / "VERIFIED"
    if not release.is_dir() or not verified.is_file():
        raise RuntimeBundleError(f"verified release is not installed: {version}")
    manifest = verify_bundle(
        release / "artifact",
        expected_repository=_expected_repository(),
    )
    try:
        marker = json.loads(verified.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeBundleError("VERIFIED marker is invalid") from exc
    venv_python = _venv_python(release / "venv")
    pyvenv_cfg = release / "venv" / "pyvenv.cfg"
    if (
        not venv_python.is_file()
        or not os.access(venv_python, os.X_OK)
        or not pyvenv_cfg.is_file()
        or pyvenv_cfg.is_symlink()
    ):
        raise RuntimeBundleError("verified venv runtime identity is missing")
    if (
        not isinstance(marker, dict)
        or marker.get("policy_version") != version
        or manifest.get("policy_version") != version
        or marker.get("manifest_sha256") != _sha256(release / "artifact" / "manifest.json")
        or marker.get("python_sha256")
        != _sha256(venv_python.resolve())
        or marker.get("pyvenv_cfg_sha256")
        != _sha256(pyvenv_cfg)
    ):
        raise RuntimeBundleError("release verification marker does not match artifact")
    _attest_installed_release(release)
    return release


def _extract_policy_version(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeBundleError(f"cannot read policy manifest: {path}") from exc
    values: list[str] = []
    for line in text.splitlines():
        match = re.fullmatch(
            r"policy_version:\s*(.+?)\s*",
            line.split("#", 1)[0],
        )
        if match:
            value = match.group(1).strip().strip("'\"")
            values.append(value)
    if len(values) != 1 or VERSION_RE.fullmatch(values[0]) is None:
        raise RuntimeBundleError(f"cannot resolve one exact policy_version from {path.name}")
    return values[0]


def select_release(root: Path, repo: Path) -> tuple[Path, dict[str, Any]]:
    canonical = repo.resolve() / ".project-policy.yml"
    legacy = repo.resolve() / ".paul-project.yml"
    if canonical.is_file():
        version = _extract_policy_version(canonical)
        if legacy.is_file() and _extract_policy_version(legacy) != version:
            raise RuntimeBundleError("policy manifest aliases disagree on policy_version")
    elif legacy.is_file():
        version = _extract_policy_version(legacy)
        print(
            "WARNING: .paul-project.yml is deprecated; migrate to .project-policy.yml",
            file=sys.stderr,
        )
    else:
        raise RuntimeBundleError("target repository has no project policy manifest")
    release = _verified_release(root, version)
    python = _venv_python(release / "venv")
    installed = _run(
        [
            str(python),
            "-P",
            "-I",
            "-c",
            "import importlib.metadata; print(importlib.metadata.version('policy-check'))",
        ],
        cwd=repo,
        env={
            key: value
            for key, value in os.environ.items()
            if key not in {"PYTHONPATH", "PYTHONHOME"}
        },
    )
    if _normalized_package_version(installed) != _normalized_package_version(version):
        raise RuntimeBundleError("installed distribution does not match selected release")
    manifest = json.loads((release / "artifact" / "manifest.json").read_text(encoding="utf-8"))
    return release, manifest


def activate(root: Path, skill_target: Path, version: str) -> None:
    runtime_root = root.resolve()
    recover(runtime_root, skill_target)
    release = _verified_release(runtime_root, version)
    _ensure_skill_target(skill_target, runtime_root)
    state_path = runtime_root / "state.json"
    state = _load_state(state_path)
    current = state.get("current") if isinstance(state.get("current"), str) else None
    current_link = runtime_root / "current"
    skill_release = release / "artifact" / "skills" / "preflight-ci"
    links_match = (
        _symlink_points_to(current_link, release)
        and _symlink_points_to(skill_target, skill_release)
        and (runtime_root / "bin" / "policy-preflight").is_file()
        and (runtime_root / "bin" / "policy-runtime-bundle").is_file()
    )
    if current == version and links_match:
        return
    new_state = dict(state)
    if current != version:
        previous = current
        new_state.update(
            {"schema_version": 1, "current": version, "previous": previous}
        )
    _switch_active_release(runtime_root, skill_target, release, new_state)


def rollback(root: Path, skill_target: Path, version: str | None) -> str:
    runtime_root = root.resolve()
    recover(runtime_root, skill_target)
    state_path = runtime_root / "state.json"
    state = _load_state(state_path, required=True)
    target = version or state.get("previous")
    if not isinstance(target, str):
        raise RuntimeBundleError("no verified previous version is recorded")
    if state.get("current") == target:
        activate(root, skill_target, target)
        return target
    activate(root, skill_target, target)
    return target


def uninstall(root: Path, version: str) -> None:
    runtime_root = root.resolve()
    recover(runtime_root)
    state_path = runtime_root / "state.json"
    state = _load_state(state_path, required=True)
    if state.get("current") == version:
        raise RuntimeBundleError("refusing to uninstall the active release")
    installed = state.get("installed")
    if (
        not isinstance(installed, list)
        or version not in installed
        or not all(isinstance(item, str) for item in installed)
    ):
        raise RuntimeBundleError("release is not owned by install state")
    if VERSION_RE.fullmatch(version) is None:
        raise RuntimeBundleError("invalid release version")
    releases = runtime_root / "releases"
    release_path = releases / version
    if release_path.is_symlink():
        raise RuntimeBundleError("installed release must not be a symlink")
    release = release_path.resolve()
    try:
        release.relative_to(releases.resolve())
    except ValueError as exc:
        raise RuntimeBundleError("release path escapes runtime root") from exc
    if not release.is_dir():
        raise RuntimeBundleError("state-owned release directory is missing")
    shutil.rmtree(release)
    remaining = [
        item
        for item in installed
        if isinstance(item, str) and item != version
    ]
    state["installed"] = remaining
    if state.get("previous") == version:
        state["previous"] = None
    _write_json_atomic(state_path, state)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="runtime-manager")
    subparsers = parser.add_subparsers(dest="command", required=True)
    install_parser = subparsers.add_parser("install")
    install_parser.add_argument("--bundle", required=True)
    install_parser.add_argument("--root")
    install_parser.add_argument("--skill-target")
    install_parser.add_argument("--force-reinstall", action="store_true")
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--bundle", required=True)
    execute_parser = subparsers.add_parser("exec")
    execute_parser.add_argument("--root")
    execute_parser.add_argument("--repo", required=True)
    execute_parser.add_argument("arguments", nargs=argparse.REMAINDER)
    rollback_parser = subparsers.add_parser("rollback")
    rollback_parser.add_argument("--root")
    rollback_parser.add_argument("--skill-target")
    rollback_parser.add_argument("--version")
    recover_parser = subparsers.add_parser("recover")
    recover_parser.add_argument("--root")
    recover_parser.add_argument("--skill-target")
    activate_parser = subparsers.add_parser("activate")
    activate_parser.add_argument("--root")
    activate_parser.add_argument("--skill-target")
    activate_parser.add_argument("--version", required=True)
    uninstall_parser = subparsers.add_parser("uninstall")
    uninstall_parser.add_argument("--root")
    uninstall_parser.add_argument("--version", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    requested_root = (
        Path(args.root).expanduser()
        if getattr(args, "root", None)
        else None
    )
    requested_skill_target = (
        Path(args.skill_target).expanduser()
        if getattr(args, "skill_target", None)
        else None
    )
    skill_target = (
        requested_skill_target or _default_skill_target()
    )
    try:
        if args.command == "verify":
            manifest = verify_bundle(
                Path(args.bundle),
                expected_repository=_expected_repository(),
            )
            print(f"BUNDLE VERIFIED {manifest['policy_version']}")
        elif args.command == "install":
            version = install(
                Path(args.bundle),
                requested_root,
                skill_target,
                force_reinstall=args.force_reinstall,
            )
            print(f"INSTALLED {version}")
        else:
            root = requested_root or _default_root()
            if args.command == "rollback":
                version = rollback(root, skill_target, args.version)
                print(f"ROLLED BACK {version}")
            elif args.command == "recover":
                recovered = recover(root, requested_skill_target)
                print("RECOVERED" if recovered else "NO RECOVERY NEEDED")
            elif args.command == "activate":
                activate(root, skill_target, args.version)
                print(f"ACTIVATED {args.version}")
            elif args.command == "uninstall":
                uninstall(root, args.version)
                print(f"UNINSTALLED {args.version}")
            elif args.command == "exec":
                repo = Path(args.repo).resolve()
                forwarded = list(args.arguments)
                if forwarded and forwarded[0] == "--":
                    forwarded = forwarded[1:]
                if any(
                    value in {"--repo", "--installed-manifest", "--engine-source"}
                    or value.startswith(
                        ("--repo=", "--installed-manifest=", "--engine-source=")
                    )
                    for value in forwarded
                ):
                    raise RuntimeBundleError(
                        "forwarded engine authority option conflicts with exact-version selection"
                    )
                release, _manifest = select_release(root, repo)
                python = _venv_python(release / "venv")
                command = [
                    str(python),
                    "-I",
                    "-m",
                    "policy_check.preflight",
                    "--repo",
                    str(repo),
                    "--installed-manifest",
                    str(release / "artifact" / "manifest.json"),
                    *forwarded,
                ]
                env = dict(os.environ)
                env.pop("PYTHONPATH", None)
                env.pop("PYTHONHOME", None)
                os.execvpe(command[0], command, env)
    except RuntimeBundleError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except (OSError, UnicodeError) as exc:
        print(
            f"ERROR: runtime I/O failure: {exc.__class__.__name__}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
