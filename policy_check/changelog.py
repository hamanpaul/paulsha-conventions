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

# A dated Keep-a-Changelog heading: "## [<version>] - <date>". Non-dated buckets
# (e.g. "## [Unreleased]" or a legacy backlog label) are intentionally NOT matched,
# so a new release section is always inserted above the newest *dated* section.
_DATED_SECTION_RE = re.compile(r"(?m)^##\s+\[[^\]]+\]\s+-\s+\d")


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
    if text.startswith("﻿"):  # tolerate a UTF-8 BOM
        text = text[1:]
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
    if issue is not None:
        # reject bool (YAML true/false) and float; accept int or a digit string
        if isinstance(issue, bool) or not isinstance(issue, (int, str)):
            raise FragmentError(f"fragment 'issue' must be an integer, got {issue!r}")
        try:
            issue = int(issue)
        except ValueError as exc:
            raise FragmentError(f"fragment 'issue' must be an integer, got {issue!r}") from exc
    return Fragment(type=ftype, body=body, scope=meta.get("scope"), issue=issue)


def _bullet(body: str) -> str:
    """Render a (possibly multi-line) body as one markdown list item.

    Continuation lines are indented two spaces so they stay within the bullet
    and the output remains valid Keep-a-Changelog markdown.
    """
    body_lines = body.split("\n")
    return "- " + "\n  ".join(body_lines)


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
        lines.extend(_bullet(body) for body in grouped[section])
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
    try:
        text = changelog_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FragmentError(f"CHANGELOG.md not found at {changelog_path}") from exc
    changelog_path.write_text(_insert_section(text, section), encoding="utf-8")
    for name, _frag in loaded:
        (repo_root / "changelog.d" / name).unlink()
    return len(loaded)


def extract_section(changelog_text: str, version: str) -> str:
    """Return the body of the dated ``## [version] - <date>`` section, heading excluded.

    Release automation reads this as the authored summary for one tag. Only dated
    sections qualify: an undated bucket such as ``## [pre-fragment backlog]`` is not
    a release. Raises FragmentError when the version is absent or its body is empty.
    """
    heading = re.compile(
        r"(?m)^##\s+\[" + re.escape(version) + r"\]\s+-\s+\d\S*\s*$"
    )
    match = heading.search(changelog_text)
    if match is None:
        raise FragmentError(f"no dated CHANGELOG section for version {version!r}")
    rest = changelog_text[match.end():]
    next_heading = re.compile(r"(?m)^##\s").search(rest)
    body = (rest[: next_heading.start()] if next_heading else rest).strip()
    if not body:
        raise FragmentError(f"CHANGELOG section for version {version!r} is empty")
    return body


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="policy-check-changelog")
    sub = parser.add_subparsers(dest="cmd", required=True)
    collate_p = sub.add_parser(
        "collate", help="Collate changelog.d/*.md into a dated CHANGELOG section")
    collate_p.add_argument("--repo", default=".")
    collate_p.add_argument("--version", required=True)
    collate_p.add_argument("--date", required=True)
    extract_p = sub.add_parser(
        "extract", help="Print one dated CHANGELOG section body (release notes source)")
    extract_p.add_argument("--repo", default=".")
    extract_p.add_argument("--version", required=True)
    args = parser.parse_args(argv)
    if args.cmd == "collate":
        count = collate(Path(args.repo), args.version, args.date)
        print(f"collated {count} fragment(s) into [{args.version}] - {args.date}")
        return 0
    if args.cmd == "extract":
        changelog_path = Path(args.repo) / "CHANGELOG.md"
        try:
            text = changelog_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            print(f"ERROR: CHANGELOG.md not found at {changelog_path}", file=sys.stderr)
            return 2
        try:
            print(extract_section(text, args.version))
        except FragmentError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
