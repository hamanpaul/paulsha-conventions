"""CHANGELOG per-PR fragment model + release collation (ops tool, NOT an R-xx rule).

Parallel agents repeatedly conflicted on the shared ``## [Unreleased]`` section of
CHANGELOG.md. Instead, each PR adds its own ``changelog.d/<issue>-<slug>.md``
fragment; at release time ``collate`` merges them into a dated Keep-a-Changelog
section and clears the directory.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

# Fixed conventional-commit type → Keep-a-Changelog section mapping.
TYPE_TO_SECTION = {
    "feat": "Added",
    "fix": "Fixed",
    "refactor": "Changed",
    "perf": "Changed",
    "change": "Changed",
    "remove": "Removed",
    "deprecate": "Deprecated",
    "security": "Security",
}
SECTION_ORDER = ["Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"]

_DATED_SECTION_RE = re.compile(r"(?m)^##\s+\[")


class FragmentError(Exception):
    """Raised when a changelog fragment is malformed or has an unknown type."""


@dataclass
class Fragment:
    type: str
    body: str
    scope: str | None = None
    issue: int | None = None


def parse_fragment(text: str) -> Fragment:
    """Parse a fragment's YAML frontmatter + body into a Fragment."""
    if not text.startswith("---"):
        raise FragmentError("fragment must start with a YAML frontmatter block")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise FragmentError("fragment frontmatter block is not closed")
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as exc:
        raise FragmentError(f"invalid frontmatter YAML: {exc}") from exc
    if not isinstance(meta, dict):
        raise FragmentError("frontmatter must be a mapping")
    ftype = meta.get("type")
    if not ftype or not isinstance(ftype, str):
        raise FragmentError("fragment frontmatter requires a string 'type'")
    body = parts[2].strip()
    if not body:
        raise FragmentError("fragment body must not be empty")
    issue = meta.get("issue")
    return Fragment(
        type=ftype,
        body=body,
        scope=meta.get("scope"),
        issue=int(issue) if issue is not None else None,
    )


def render_section(version: str, date: str, fragments: list[Fragment]) -> str:
    """Render fragments into a dated Keep-a-Changelog section string.

    Raises FragmentError if any fragment has a type outside TYPE_TO_SECTION.
    """
    grouped: dict[str, list[str]] = {}
    for frag in fragments:
        section = TYPE_TO_SECTION.get(frag.type)
        if section is None:
            raise FragmentError(
                f"unknown fragment type {frag.type!r}; allowed: {sorted(TYPE_TO_SECTION)}"
            )
        grouped.setdefault(section, []).append(frag.body)
    lines = [f"## [{version}] - {date}", ""]
    for section in SECTION_ORDER:
        if section not in grouped:
            continue
        lines.append(f"### {section}")
        lines.extend(f"- {body}" for body in grouped[section])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def load_fragments(repo_root: Path) -> list[tuple[str, Fragment]]:
    """Return (filename, Fragment) for each changelog.d/*.md, sorted by filename."""
    directory = repo_root / "changelog.d"
    if not directory.is_dir():
        return []
    out: list[tuple[str, Fragment]] = []
    for path in sorted(directory.glob("*.md")):
        out.append((path.name, parse_fragment(path.read_text(encoding="utf-8"))))
    return out


def _insert_section(changelog_text: str, section: str) -> str:
    """Insert ``section`` before the first dated ``## [`` heading; else append."""
    match = _DATED_SECTION_RE.search(changelog_text)
    block = section.rstrip() + "\n\n"
    if match:
        return changelog_text[: match.start()] + block + changelog_text[match.start():]
    return changelog_text.rstrip() + "\n\n" + block


def collate(repo_root: Path, version: str, date: str) -> int:
    """Collate changelog.d/*.md into a dated CHANGELOG section; return fragment count.

    No-op (returns 0) when there are no fragments. Raises FragmentError on a
    malformed fragment or unknown type, leaving files untouched.
    """
    loaded = load_fragments(repo_root)
    if not loaded:
        return 0
    fragments = [frag for _name, frag in loaded]
    section = render_section(version, date, fragments)  # raises before any write
    changelog_path = repo_root / "CHANGELOG.md"
    text = changelog_path.read_text(encoding="utf-8")
    changelog_path.write_text(_insert_section(text, section), encoding="utf-8")
    for name, _frag in loaded:
        (repo_root / "changelog.d" / name).unlink()
    return len(loaded)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="policy-check-changelog")
    sub = parser.add_subparsers(dest="cmd", required=True)
    collate_p = sub.add_parser(
        "collate", help="Collate changelog.d/*.md into a dated CHANGELOG section")
    collate_p.add_argument("--repo", default=".")
    collate_p.add_argument("--version", required=True)
    collate_p.add_argument("--date", required=True)
    args = parser.parse_args(argv)
    if args.cmd == "collate":
        count = collate(Path(args.repo), args.version, args.date)
        print(f"collated {count} fragment(s) into [{args.version}] - {args.date}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
