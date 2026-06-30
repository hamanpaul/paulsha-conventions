# policy_check/doc_drift/exempt.py
from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch

_MARKER = "doc-drift-ignore"


def line_is_ignored(line: str) -> bool:
    return _MARKER in line


@dataclass
class Allowlist:
    symbols: set[str] = field(default_factory=set)
    path_globs: list[str] = field(default_factory=list)


def parse_allowlist(lines) -> Allowlist:
    al = Allowlist()
    for raw in lines:
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("symbol:"):
            al.symbols.add(s[len("symbol:"):])
        else:
            al.path_globs.append(s)
    return al


def is_allowed(doc_rel: str, token: str, allow: Allowlist) -> bool:
    if token in allow.symbols:
        return True
    return any(fnmatch(doc_rel, g) for g in allow.path_globs)
