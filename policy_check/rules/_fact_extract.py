"""Shared, deterministic public-fact extractors for the doc-coverage rule.

v1 supports four built-in extractor kinds with fixed fact identities:

| kind        | required fields      | fact identity                              |
|-------------|----------------------|--------------------------------------------|
| modules     | include [, exclude]  | repo-relative POSIX path (e.g. pkg/a.py)   |
| rpc_methods | include, pattern     | the single regex capture group             |
| env_vars    | include, prefix      | the matched ``PREFIX[A-Z0-9_]+`` token     |
| cli_tree    | command              | one full command path per stdout line      |

Extraction is intentionally config-driven: the engine never guesses a repo's
public surface, it only enumerates what the repo explicitly declares.
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess
from fnmatch import fnmatch
from typing import Callable, Optional

VALID_KINDS = ("modules", "rpc_methods", "env_vars", "cli_tree")
FILE_KINDS = ("modules", "rpc_methods", "env_vars")
COMMAND_KINDS = ("cli_tree",)

_COMMAND_TIMEOUT = 30

# Characters that can be part of a fact-like token; used to enforce exact
# token/phrase boundaries so a substring never counts as a mention.
_BOUNDARY = r"A-Za-z0-9_./-"


class ExtractorError(Exception):
    """Raised when an extractor cannot produce a deterministic fact set."""


def validate_source(source: object) -> Optional[str]:
    """Return an error string if ``source`` is not a valid extractor config, else None."""
    if not isinstance(source, dict):
        return "source must be a mapping/object"
    kind = source.get("kind")
    if kind not in VALID_KINDS:
        return f"kind must be one of {list(VALID_KINDS)}, got {kind!r}"

    if kind in FILE_KINDS:
        include = source.get("include")
        if not isinstance(include, list) or not include or not all(isinstance(x, str) for x in include):
            return f"{kind} requires a non-empty 'include' list of globs"
        exclude = source.get("exclude")
        if exclude is not None and (
            not isinstance(exclude, list) or not all(isinstance(x, str) for x in exclude)
        ):
            return f"{kind} 'exclude' must be a list of globs"

    if kind == "rpc_methods":
        pattern = source.get("pattern")
        if not isinstance(pattern, str) or not pattern:
            return "rpc_methods requires a 'pattern' string"
        try:
            compiled = re.compile(pattern)
        except re.error as exc:
            return f"rpc_methods 'pattern' is not a valid regex: {exc}"
        if compiled.groups != 1:
            return "rpc_methods 'pattern' must have exactly one capture group"

    if kind == "env_vars":
        prefix = source.get("prefix")
        if not isinstance(prefix, str) or not prefix:
            return "env_vars requires a 'prefix' string"

    if kind == "cli_tree":
        command = source.get("command")
        if not isinstance(command, str) or not command.strip():
            return "cli_tree requires a 'command' string"

    return None


def _match_files(files, include: list[str], exclude: list[str]) -> list[str]:
    out = []
    for rel in files:
        if not any(fnmatch(rel, pat) for pat in include):
            continue
        if exclude and any(fnmatch(rel, pat) for pat in exclude):
            continue
        out.append(rel)
    return sorted(out)


def extract_file_facts(
    source: dict,
    files,
    read_file: Callable[[str], Optional[str]],
) -> set[str]:
    """Extract facts for a file-scanning extractor against one repo snapshot.

    ``files`` is the iterable of repo-relative paths tracked in that snapshot;
    ``read_file(rel)`` returns the file's text or None when unreadable/absent.
    """
    kind = source["kind"]
    include = source.get("include") or []
    exclude = source.get("exclude") or []
    matched = _match_files(files, include, exclude)

    if kind == "modules":
        return set(matched)

    facts: set[str] = set()
    if kind == "rpc_methods":
        compiled = re.compile(source["pattern"])
        for rel in matched:
            text = read_file(rel)
            if text is None:
                continue
            for m in compiled.finditer(text):
                value = m.group(1)
                if value:  # drop non-participating / empty captures
                    facts.add(value)
    elif kind == "env_vars":
        prefix = source["prefix"]
        # left boundary so the prefix starts a token (not pulled out of a longer identifier)
        token = re.compile(r"(?<![A-Z0-9_])" + re.escape(prefix) + r"[A-Z0-9_]+")
        for rel in matched:
            text = read_file(rel)
            if text is None:
                continue
            for m in token.finditer(text):
                facts.add(m.group(0))
    return facts


def extract_cli_facts(source: dict, repo_root) -> set[str]:
    """Run a ``cli_tree`` command and return one fact per non-empty stdout line."""
    cmd = shlex.split(str(source["command"]))
    env = {**os.environ, "LC_ALL": "C"}
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(repo_root),
            env=env,
            capture_output=True,
            timeout=_COMMAND_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ExtractorError(f"cli_tree command failed to run: {exc}") from exc
    if proc.returncode != 0:
        raise ExtractorError(f"cli_tree command exit={proc.returncode} for {cmd!r}")
    out = proc.stdout.decode("utf-8", "replace")
    return {line.strip() for line in out.splitlines() if line.strip()}


def is_mentioned(fact: str, text: str) -> bool:
    """True iff ``fact`` appears in ``text`` as a whole token/phrase.

    Matching is case-sensitive and boundary-guarded so a longer token never
    counts as a mention of a shorter one (e.g. ``session.closed`` does not
    satisfy ``session.close``).
    """
    if not fact:
        return False
    pattern = rf"(?<![{_BOUNDARY}]){re.escape(fact)}(?![{_BOUNDARY}])"
    return re.search(pattern, text) is not None
