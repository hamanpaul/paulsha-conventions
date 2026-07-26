from __future__ import annotations

import argparse
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


# The source package and the vendored bootstrap use one stdlib-only verifier.
# A copied manager loads its checksummed sibling explicitly because Python -I
# deliberately omits the script directory from sys.path.
try:
    from .verification import (
        VERSION_RE,
        BundleError as RuntimeBundleError,
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
    verify_bundle = _verifier.load_and_verify_bundle
    _normalized_package_version = _verifier.normalized_package_version
    _sha256 = _verifier.sha256_file
    _verify_installed_wheels = _verifier.verify_installed_wheel_payload


def _default_root() -> Path:
    configured = os.environ.get("PSC_CONVENTIONS_ROOT")
    if configured:
        return Path(configured).expanduser()
    data_home = os.environ.get("XDG_DATA_HOME")
    if data_home:
        return Path(data_home).expanduser() / "paulsha-conventions"
    return Path.home() / ".local" / "share" / "paulsha-conventions"


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


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{uuid.uuid4().hex}")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


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
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.restore-{uuid.uuid4().hex}")
    temporary.write_bytes(content)
    temporary.chmod(mode)
    os.replace(temporary, path)


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
    )


def _install_launcher(root: Path, release: Path) -> None:
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
    text = (
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
    temporary = launcher.with_name(f".{launcher.name}.tmp-{uuid.uuid4().hex}")
    temporary.write_text(text, encoding="utf-8")
    temporary.chmod(0o755)
    os.replace(temporary, launcher)

    lifecycle = root / "bin" / "policy-runtime-bundle"
    lifecycle_text = (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'RUNTIME_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"\n'
        'COMMAND="${1:-}"\n'
        '[[ -n "$COMMAND" ]] || { '
        'echo "ERROR: expected install, activate, rollback, or uninstall" >&2; exit 2; }\n'
        "shift\n"
        'case "$COMMAND" in\n'
        '  install|activate|rollback|uninstall) ;;\n'
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
    temporary = lifecycle.with_name(
        f".{lifecycle.name}.tmp-{uuid.uuid4().hex}"
    )
    temporary.write_text(lifecycle_text, encoding="utf-8")
    temporary.chmod(0o755)
    os.replace(temporary, lifecycle)


def _switch_active_release(
    runtime_root: Path,
    skill_target: Path,
    release: Path,
    state: dict[str, Any],
) -> None:
    state_path = runtime_root / "state.json"
    current_link = runtime_root / "current"
    preflight_launcher = runtime_root / "bin" / "policy-preflight"
    lifecycle_launcher = runtime_root / "bin" / "policy-runtime-bundle"
    snapshots = {
        "state": _snapshot_regular_file(state_path),
        "current": _snapshot_symlink(current_link),
        "preflight": _snapshot_regular_file(preflight_launcher),
        "lifecycle": _snapshot_regular_file(lifecycle_launcher),
        "skill": _snapshot_symlink(skill_target),
    }
    try:
        _write_json_atomic(state_path, state)
        _atomic_symlink(release, current_link)
        _install_launcher(runtime_root, release)
        _atomic_symlink(
            release / "artifact" / "skills" / "preflight-ci",
            skill_target,
        )
    except BaseException as exc:
        failures: list[str] = []
        restorations = (
            ("skill", lambda: _restore_symlink(skill_target, snapshots["skill"])),
            (
                "lifecycle launcher",
                lambda: _restore_regular_file(
                    lifecycle_launcher,
                    snapshots["lifecycle"],
                ),
            ),
            (
                "preflight launcher",
                lambda: _restore_regular_file(
                    preflight_launcher,
                    snapshots["preflight"],
                ),
            ),
            (
                "current",
                lambda: _restore_symlink(current_link, snapshots["current"]),
            ),
            (
                "state",
                lambda: _restore_regular_file(state_path, snapshots["state"]),
            ),
        )
        for label, restore in restorations:
            try:
                restore()
            except (OSError, RuntimeBundleError) as restore_exc:
                failures.append(f"{label} ({restore_exc.__class__.__name__})")
        if failures:
            raise RuntimeBundleError(
                "activation failed and managed state rollback was incomplete: "
                + ", ".join(failures)
            ) from exc
        raise


def install(
    bundle: Path,
    root: Path,
    skill_target: Path,
    *,
    force_reinstall: bool = False,
) -> str:
    manifest = verify_bundle(bundle)
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
    runtime_root = root.resolve()
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
        verify_bundle(staging / "artifact")
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
    manifest = verify_bundle(release / "artifact")
    try:
        marker = json.loads(verified.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeBundleError("VERIFIED marker is invalid") from exc
    if (
        not isinstance(marker, dict)
        or marker.get("policy_version") != version
        or manifest.get("policy_version") != version
        or marker.get("manifest_sha256") != _sha256(release / "artifact" / "manifest.json")
    ):
        raise RuntimeBundleError("release verification marker does not match artifact")
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
    _attest_installed_release(release)
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
    state_path = root.resolve() / "state.json"
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
    root = Path(args.root).expanduser() if getattr(args, "root", None) else _default_root()
    skill_target = (
        Path(args.skill_target).expanduser()
        if getattr(args, "skill_target", None)
        else _default_skill_target()
    )
    try:
        if args.command == "verify":
            manifest = verify_bundle(Path(args.bundle))
            print(f"BUNDLE VERIFIED {manifest['policy_version']}")
        elif args.command == "install":
            version = install(
                Path(args.bundle),
                root,
                skill_target,
                force_reinstall=args.force_reinstall,
            )
            print(f"INSTALLED {version}")
        elif args.command == "rollback":
            version = rollback(root, skill_target, args.version)
            print(f"ROLLED BACK {version}")
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
