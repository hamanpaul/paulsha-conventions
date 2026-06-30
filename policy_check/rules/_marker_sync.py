"""Shared marker-sync + command-execution helpers.

Generalizes the marker/exec pattern originally embedded in R-16 (CLI help sync)
so it can back both the existing ``cli-help`` markers and the generic
``generated-fact`` markers introduced for issue #26, without forcing existing
repos to migrate their CLI help blocks.

Execution contract (fixed): ``shlex.split`` with no shell, ``cwd=repo_root``,
``LC_ALL=C`` in the environment, and a fixed timeout.
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess

DEFAULT_TIMEOUT = 30


def marker_block(text: str, marker: str, tag: str = "generated-fact") -> tuple[bool, str]:
    """Return ``(found, inner_text)`` for a ``<tag> marker="<marker>"`` block."""
    pattern = (
        rf"<!--\s*BEGIN:\s*{re.escape(tag)}\s+marker=\"{re.escape(marker)}\"\s*-->"
        rf"(.*?)"
        rf"<!--\s*END:\s*{re.escape(tag)}\s+marker=\"{re.escape(marker)}\"\s*-->"
    )
    match = re.search(pattern, text, flags=re.DOTALL)
    if not match:
        return False, ""
    return True, match.group(1)


def normalize(text: str) -> str:
    return text.strip()


class CommandResult:
    def __init__(self, returncode: int, stdout: str, stderr: str) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def run_command(command: str, repo_root, extra_args=None, timeout: int = DEFAULT_TIMEOUT) -> CommandResult:
    """Run ``command`` deterministically and return decoded stdout/stderr.

    Raises ``OSError`` / ``subprocess.SubprocessError`` (incl. ``TimeoutExpired``)
    on failure to launch or complete; callers translate those into a rule FAIL.
    """
    cmd = [*shlex.split(str(command)), *(extra_args or [])]
    env = {**os.environ, "LC_ALL": "C"}
    proc = subprocess.run(
        cmd,
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return CommandResult(
        proc.returncode,
        proc.stdout.decode("utf-8", "replace"),
        proc.stderr.decode("utf-8", "replace"),
    )
