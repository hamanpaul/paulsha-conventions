# policy_check/doc_drift/exempt.py
from __future__ import annotations

import re
from dataclasses import dataclass, field
from fnmatch import fnmatch

# 僅承認 HTML 註解形式的 marker，避免內文／反引號裡字面提到 doc-drift-ignore
# 時誤抑制同一行的真實引用。
_MARKER_RE = re.compile(r"<!--\s*doc-drift-ignore\s*-->")


def line_is_ignored(line: str) -> bool:
    return bool(_MARKER_RE.search(line))


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
