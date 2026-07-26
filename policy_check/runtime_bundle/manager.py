from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
import venv
from pathlib import Path, PurePosixPath
from typing import Any, Sequence


# This module is deliberately stdlib-only: a verified copy is executed before
# policy-check and PyYAML exist in the destination venv.
SCHEMA_VERSION = 1
CANONICAL_REPOSITORY = "hamanpaul/paulsha-conventions"
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:-fix\.\d+)?$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class RuntimeBundleError(RuntimeError):
    pass


def _normalized_package_version(value: str) -> str:
    return re.sub(r"-fix\.(\d+)$", r".post\1", value)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative(value: object, field: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise RuntimeBundleError(f"{field} is not a safe relative path")
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise RuntimeBundleError(f"{field} contains traversal or dot segments")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise RuntimeBundleError(f"{field} contains traversal or dot segments")
    return path


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise RuntimeBundleError("bundle payload cannot contain symlinks")
        if path.is_file():
            files.append(path)
    for path in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(_sha256(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def verify_bundle(root: Path) -> dict[str, Any]:
    bundle = root.resolve()
    sums = bundle / "SHA256SUMS"
    try:
        lines = sums.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise RuntimeBundleError("SHA256SUMS is unreadable") from exc
    expected: dict[str, str] = {}
    for number, line in enumerate(lines, start=1):
        if not line:
            continue
        if "  " not in line:
            raise RuntimeBundleError(f"invalid SHA256SUMS line {number}")
        digest, raw_name = line.split("  ", 1)
        name = _safe_relative(raw_name, f"SHA256SUMS line {number}").as_posix()
        if SHA256_RE.fullmatch(digest) is None or name in expected:
            raise RuntimeBundleError(f"invalid or duplicate checksum line {number}")
        expected[name] = digest
    actual: set[str] = set()
    for path in bundle.rglob("*"):
        if path.is_symlink():
            raise RuntimeBundleError("bundle contains a symlink")
        if path.is_file() and path != sums:
            actual.add(path.relative_to(bundle).as_posix())
    if set(expected) != actual:
        raise RuntimeBundleError("bundle file set does not match SHA256SUMS")
    for name, digest in expected.items():
        if _sha256(bundle / name) != digest:
            raise RuntimeBundleError(f"checksum mismatch: {name}")
    try:
        manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeBundleError("manifest.json is invalid") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != SCHEMA_VERSION:
        raise RuntimeBundleError("unsupported manifest schema")
    version = manifest.get("policy_version")
    package = manifest.get("package")
    if (
        not isinstance(version, str)
        or VERSION_RE.fullmatch(version) is None
        or manifest.get("skill_version") != version
        or manifest.get("release_tag") != f"v{version}"
        or manifest.get("repository") != CANONICAL_REPOSITORY
        or FULL_SHA_RE.fullmatch(str(manifest.get("release_commit") or "")) is None
        or not isinstance(package, dict)
        or package.get("name") != "policy-check"
        or package.get("version") != _normalized_package_version(version)
    ):
        raise RuntimeBundleError("manifest identity is inconsistent")
    wheels = manifest.get("wheels")
    if not isinstance(wheels, list) or not wheels:
        raise RuntimeBundleError("manifest has no wheels")
    for wheel in wheels:
        if not isinstance(wheel, dict):
            raise RuntimeBundleError("invalid wheel entry")
        name = _safe_relative(wheel.get("path"), "wheel.path").as_posix()
        if expected.get(name) != wheel.get("sha256"):
            raise RuntimeBundleError(f"wheel identity mismatch: {name}")
    skill = manifest.get("skill")
    runtime = manifest.get("runtime")
    if not isinstance(skill, dict) or not isinstance(runtime, dict):
        raise RuntimeBundleError("manifest payload identity is incomplete")
    skill_root = bundle / _safe_relative(skill.get("path"), "skill.path")
    runtime_path = bundle / _safe_relative(runtime.get("path"), "runtime.path")
    if _tree_hash(skill_root) != skill.get("sha256"):
        raise RuntimeBundleError("skill payload hash mismatch")
    if _sha256(runtime_path) != runtime.get("sha256"):
        raise RuntimeBundleError("runtime manager hash mismatch")
    return manifest


def _default_root() -> Path:
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
        raise RuntimeBundleError(f"command failed ({result.returncode}): {argv[0]}")
    return result.stdout.strip()


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{uuid.uuid4().hex}")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


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
    _run(["git", "init", "-q", "-b", "main"], cwd=repo)
    _run(["git", "config", "user.email", "runtime@example.invalid"], cwd=repo)
    _run(["git", "config", "user.name", "Runtime Bundle"], cwd=repo)
    _run(["git", "add", "."], cwd=repo)
    _run(["git", "commit", "-qm", "chore: runtime smoke baseline"], cwd=repo)
    _run(["git", "tag", "-a", f"v{version}", "-m", f"v{version}"], cwd=repo)
    _run(["git", "update-ref", "refs/remotes/origin/main", "HEAD"], cwd=repo)
    _run(["git", "switch", "-qc", "feature/runtime-smoke"], cwd=repo)
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
        f'RUNTIME_ROOT="${{PSC_CONVENTIONS_ROOT:-{root}}}"\n'
        'MANAGER="$RUNTIME_ROOT/current/artifact/runtime/runtime_manager.py"\n'
        '[[ -f "$MANAGER" ]] || { echo "ERROR: no active runtime manager" >&2; exit 2; }\n'
        'exec python3 -P "$MANAGER" exec --root "$RUNTIME_ROOT" --repo "$PWD" -- "$@"\n'
    )
    temporary = launcher.with_name(f".{launcher.name}.tmp-{uuid.uuid4().hex}")
    temporary.write_text(text, encoding="utf-8")
    temporary.chmod(0o755)
    os.replace(temporary, launcher)


def install(bundle: Path, root: Path, skill_target: Path) -> str:
    manifest = verify_bundle(bundle)
    version = manifest["policy_version"]
    runtime_root = root.resolve()
    releases = runtime_root / "releases"
    destination = releases / version
    _ensure_skill_target(skill_target, runtime_root)
    if destination.exists() or destination.is_symlink():
        raise RuntimeBundleError(f"release already installed: {version}")
    releases.mkdir(parents=True, exist_ok=True)
    staging = releases / f".staging-{version}-{uuid.uuid4().hex}"
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
        os.replace(staging, destination)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise

    state_path = runtime_root / "state.json"
    previous: str | None = None
    if state_path.is_file():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            if isinstance(state, dict) and isinstance(state.get("current"), str):
                previous = state["current"]
        except (OSError, UnicodeError, json.JSONDecodeError):
            raise RuntimeBundleError("existing state.json is invalid")
    _atomic_symlink(destination, runtime_root / "current")
    _write_json_atomic(
        state_path,
        {
            "schema_version": 1,
            "current": version,
            "previous": previous,
            "installed": sorted(
                path.name
                for path in releases.iterdir()
                if path.is_dir() and not path.name.startswith(".staging-")
            ),
        },
    )
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
        match = re.fullmatch(r"policy_version:\s*([^#]+?)\s*", line)
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
            "-c",
            "import importlib.metadata; print(importlib.metadata.version('policy-check'))",
        ],
        cwd=repo,
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
    state: dict[str, Any] = {}
    if state_path.is_file():
        try:
            loaded = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise RuntimeBundleError("state.json is invalid") from exc
        if isinstance(loaded, dict):
            state = loaded
    previous = state.get("current") if isinstance(state.get("current"), str) else None
    _atomic_symlink(release, runtime_root / "current")
    state.update({"schema_version": 1, "current": version, "previous": previous})
    _write_json_atomic(state_path, state)
    _install_launcher(runtime_root)
    _atomic_symlink(
        runtime_root / "current" / "artifact" / "skills" / "preflight-ci",
        skill_target,
    )


def rollback(root: Path, skill_target: Path, version: str | None) -> str:
    state_path = root.resolve() / "state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeBundleError("cannot read rollback state") from exc
    target = version or (state.get("previous") if isinstance(state, dict) else None)
    if not isinstance(target, str):
        raise RuntimeBundleError("no verified previous version is recorded")
    activate(root, skill_target, target)
    return target


def uninstall(root: Path, skill_target: Path, version: str) -> None:
    runtime_root = root.resolve()
    state_path = runtime_root / "state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeBundleError("cannot read install state") from exc
    if state.get("current") == version:
        raise RuntimeBundleError("refusing to uninstall the active release")
    release = _verified_release(runtime_root, version)
    try:
        release.relative_to(runtime_root / "releases")
    except ValueError as exc:
        raise RuntimeBundleError("release path escapes runtime root") from exc
    shutil.rmtree(release)
    installed = [
        item
        for item in state.get("installed", [])
        if isinstance(item, str) and item != version
    ]
    state["installed"] = installed
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
    uninstall_parser.add_argument("--skill-target")
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
            version = install(Path(args.bundle), root, skill_target)
            print(f"INSTALLED {version}")
        elif args.command == "rollback":
            version = rollback(root, skill_target, args.version)
            print(f"ROLLED BACK {version}")
        elif args.command == "uninstall":
            uninstall(root, skill_target, args.version)
            print(f"UNINSTALLED {args.version}")
        elif args.command == "exec":
            repo = Path(args.repo).resolve()
            release, _manifest = select_release(root, repo)
            python = _venv_python(release / "venv")
            forwarded = list(args.arguments)
            if forwarded and forwarded[0] == "--":
                forwarded = forwarded[1:]
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
