#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C

usage() {
  cat <<'USAGE'
Usage:
  scripts/update-cli-help.sh [--repo PATH] [--dry-run] [--apply] [--help]

Description:
  Read .paul-project.yml -> cli entries, execute each command help output,
  and update corresponding marker block in reflected docs file.

Options:
  --repo PATH  Repository root. Default: current directory.
  --dry-run    Preview changes without writing files. (default)
  --apply      Write updated marker blocks to files.
  --help       Show this help.
USAGE
}

REPO_ROOT="."
APPLY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      [[ $# -ge 2 ]] || { echo "ERROR: --repo requires value" >&2; exit 1; }
      REPO_ROOT="$2"
      shift 2
      ;;
    --apply)
      APPLY=1
      shift
      ;;
    --dry-run)
      APPLY=0
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

REPO_ROOT="$(cd "$REPO_ROOT" && pwd)"
CONFIG_PATH="$REPO_ROOT/.paul-project.yml"
[[ -f "$CONFIG_PATH" ]] || { echo "ERROR: missing config: $CONFIG_PATH" >&2; exit 1; }

python3 - "$REPO_ROOT" "$APPLY" <<'PY'
from __future__ import annotations

import difflib
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import yaml

repo_root = Path(sys.argv[1])
apply = bool(int(sys.argv[2]))

cfg_path = repo_root / ".paul-project.yml"
try:
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
except yaml.YAMLError as exc:
    print(f"ERROR: invalid YAML in {cfg_path}: {exc}", file=sys.stderr)
    raise SystemExit(2)

entries = cfg.get("cli") or []
if not isinstance(entries, list):
    print("ERROR: .paul-project.yml key 'cli' must be a list", file=sys.stderr)
    raise SystemExit(2)

if not entries:
    print("CLI entries: 0")
    print("No changes.")
    raise SystemExit(0)

begin_tpl = "<!-- BEGIN: cli-help marker=\"{marker}\" -->"
end_tpl = "<!-- END: cli-help marker=\"{marker}\" -->"

changed_files: dict[Path, str] = {}
failures: list[str] = []

for idx, entry in enumerate(entries, start=1):
    if not isinstance(entry, dict):
        failures.append(f"entry[{idx}] invalid type: {type(entry).__name__}")
        continue

    command = entry.get("command")
    reflected_in = entry.get("reflected_in")
    marker = entry.get("marker")
    help_args = entry.get("help_args", ["--help"])
    exit_ok = entry.get("exit_ok", [0])
    install_cmd = entry.get("install_cmd")

    if not command or not reflected_in or not marker:
        failures.append(f"entry[{idx}] missing required keys command/reflected_in/marker")
        continue

    if isinstance(help_args, str):
        help_args = [help_args]
    elif not isinstance(help_args, list):
        failures.append(f"entry[{idx}] help_args must be string or list")
        continue

    if isinstance(exit_ok, int):
        exit_ok = [exit_ok]
    if not isinstance(exit_ok, list):
        failures.append(f"entry[{idx}] exit_ok must be int or list[int]")
        continue
    try:
        exit_ok = [int(x) for x in exit_ok]
    except Exception:
        failures.append(f"entry[{idx}] exit_ok contains non-int values")
        continue

    env = {**os.environ, "LC_ALL": "C"}

    if install_cmd:
        proc = subprocess.run(
            install_cmd,
            cwd=repo_root,
            env=env,
            shell=True,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            failures.append(
                f"entry[{idx}] install_cmd failed: {install_cmd}\n{proc.stderr.strip()}"
            )
            continue

    cmd = [*shlex.split(str(command)), *[str(a) for a in help_args]]
    try:
        proc = subprocess.run(
            cmd,
            cwd=repo_root,
            env=env,
            shell=False,
            capture_output=True,
        )
    except OSError as exc:
        failures.append(f"entry[{idx}] command failed to run: {exc}")
        continue

    if proc.returncode not in exit_ok:
        failures.append(
            f"entry[{idx}] command exit={proc.returncode} not in {exit_ok} for {cmd!r}"
        )
        continue

    output = (proc.stdout + proc.stderr).decode("utf-8", "replace").strip()

    target = repo_root / str(reflected_in)
    if target in changed_files:
        text = changed_files[target]
    elif target.exists():
        text = target.read_text(encoding="utf-8")
    else:
        failures.append(f"entry[{idx}] reflected_in not found: {reflected_in}")
        continue

    begin = begin_tpl.format(marker=marker)
    end = end_tpl.format(marker=marker)

    bi = text.find(begin)
    if bi < 0:
        failures.append(f"entry[{idx}] BEGIN marker not found for marker={marker!r} in {reflected_in}")
        continue
    start = bi + len(begin)

    ei = text.find(end, start)
    if ei < 0:
        failures.append(f"entry[{idx}] END marker not found for marker={marker!r} in {reflected_in}")
        continue

    replacement = f"\n{output}\n"
    new_text = text[:start] + replacement + text[ei:]
    changed_files[target] = new_text

if failures:
    print("ERROR: update-cli-help failed:", file=sys.stderr)
    for item in failures:
        print(f"- {item}", file=sys.stderr)
    raise SystemExit(3)

if not changed_files:
    print("No marker blocks updated.")
    raise SystemExit(0)

for path, new_text in sorted(changed_files.items()):
    old_text = path.read_text(encoding="utf-8") if path.exists() else ""
    if old_text == new_text:
        print(f"UNCHANGED {path.relative_to(repo_root)}")
        continue

    rel = path.relative_to(repo_root)
    print(f"UPDATE {rel}")
    if not apply:
        diff = difflib.unified_diff(
            old_text.splitlines(),
            new_text.splitlines(),
            fromfile=f"a/{rel}",
            tofile=f"b/{rel}",
            lineterm="",
        )
        for line in diff:
            print(line)
    else:
        path.write_text(new_text, encoding="utf-8")

print("Done." if apply else "Dry-run complete.")
PY
