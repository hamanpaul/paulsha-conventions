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
# A copied manager loads its checksummed sibling explicitly because Python -P
# deliberately omits the script directory from sys.path.
try:
    from .verification import (
        VERSION_RE,
        BundleError as RuntimeBundleError,
        load_and_verify_bundle as verify_bundle,
        normalized_package_version as _normalized_package_version,
        sha256_file as _sha256,
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
        details = (result.stderr or result.stdout).strip().splitlines()
        suffix = f": {details[-1][:500]}" if details else ""
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
                "-P",
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


def _install_launcher(root: Path) -> None:
    launcher = root / "bin" / "policy-preflight"
    launcher.parent.mkdir(parents=True, exist_ok=True)
    text = (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'RUNTIME_ROOT="${PSC_CONVENTIONS_ROOT:-'
        '$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"\n'
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
        '"$PYTHON_BIN" -c \'import sys; raise SystemExit(0 if '
        'sys.version_info >= (3, 11) else 1)\' || { '
        'echo "ERROR: Python 3.11+ is required by the runtime bundle" >&2; exit 2; }\n'
        'exec "$PYTHON_BIN" -P "$MANAGER" exec --root "$RUNTIME_ROOT" '
        '--repo "$TARGET_REPO" -- "$@"\n'
    )
    temporary = launcher.with_name(f".{launcher.name}.tmp-{uuid.uuid4().hex}")
    temporary.write_text(text, encoding="utf-8")
    temporary.chmod(0o755)
    os.replace(temporary, launcher)


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
    releases.mkdir(parents=True, exist_ok=True)
    staging = releases / f".staging-{version}-{uuid.uuid4().hex}"
    displaced: Path | None = None
    try:
        (staging / "artifact").parent.mkdir(parents=True)
        shutil.copytree(bundle.resolve(), staging / "artifact")
        verify_bundle(staging / "artifact")
        venv.EnvBuilder(with_pip=True, clear=False).create(staging / "venv")
        python = _venv_python(staging / "venv")
        wheel_dir = staging / "artifact" / "wheels"
        package_version = manifest["package"]["version"]
        _run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--find-links",
                str(wheel_dir),
                f"policy-check=={package_version}",
            ],
            cwd=staging,
        )
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
            shutil.rmtree(displaced)
            displaced = None
        else:
            os.replace(staging, destination)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        if displaced is not None and displaced.exists() and not destination.exists():
            os.replace(displaced, destination)
        raise

    _write_json_atomic(
        state_path,
        {
            "schema_version": 1,
            "current": version,
            "previous": previous,
            "installed": sorted(
                path.name
                for path in releases.iterdir()
                if path.is_dir() and not path.name.startswith(".")
            ),
        },
    )
    _atomic_symlink(destination, runtime_root / "current")
    _install_launcher(runtime_root)
    _atomic_symlink(
        runtime_root / "current" / "artifact" / "skills" / "preflight-ci",
        skill_target,
    )
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
    if current == version:
        return
    previous = current
    state.update({"schema_version": 1, "current": version, "previous": previous})
    _write_json_atomic(state_path, state)
    _atomic_symlink(release, runtime_root / "current")
    _install_launcher(runtime_root)
    _atomic_symlink(
        runtime_root / "current" / "artifact" / "skills" / "preflight-ci",
        skill_target,
    )


def rollback(root: Path, skill_target: Path, version: str | None) -> str:
    state_path = root.resolve() / "state.json"
    state = _load_state(state_path, required=True)
    target = version or state.get("previous")
    if not isinstance(target, str):
        raise RuntimeBundleError("no verified previous version is recorded")
    if state.get("current") == target:
        raise RuntimeBundleError(f"release is already active: {target}")
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
                "-P",
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
