from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .builder import build_bundle
from .integrity import (
    BundleError,
    extract_verified_archive,
    load_and_verify_bundle,
)
from .manager import main as manager_main


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="policy-runtime-bundle")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="Build from a clean annotated tag")
    build.add_argument("--repo", default=".")
    build.add_argument("--output-dir", required=True)
    build.add_argument("--tag", required=True)
    verify = subparsers.add_parser("verify", help="Verify an unpacked bundle")
    verify.add_argument("--bundle", required=True)
    extract = subparsers.add_parser(
        "extract",
        help="Verify archive digest/members and extract atomically",
    )
    extract.add_argument("--archive", required=True)
    extract.add_argument("--sha256", required=True)
    extract.add_argument("--output-dir", required=True)
    install = subparsers.add_parser("install")
    install.add_argument("--bundle", required=True)
    install.add_argument("--root")
    install.add_argument("--skill-target")
    install.add_argument("--force-reinstall", action="store_true")
    rollback = subparsers.add_parser("rollback")
    rollback.add_argument("--root")
    rollback.add_argument("--skill-target")
    rollback.add_argument("--version")
    activate = subparsers.add_parser("activate")
    activate.add_argument("--root")
    activate.add_argument("--skill-target")
    activate.add_argument("--version", required=True)
    uninstall = subparsers.add_parser("uninstall")
    uninstall.add_argument("--root")
    uninstall.add_argument("--version", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "build":
            archive, digest = build_bundle(
                Path(args.repo),
                Path(args.output_dir),
                args.tag,
            )
            print(f"BUNDLE {archive}")
            print(f"SHA256 {digest}")
        elif args.command == "verify":
            manifest = load_and_verify_bundle(Path(args.bundle))
            print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
        elif args.command == "extract":
            extracted = extract_verified_archive(
                Path(args.archive),
                Path(args.output_dir),
                args.sha256,
            )
            print(f"EXTRACTED {extracted}")
        else:
            forwarded: list[str] = []
            if args.command == "install":
                forwarded.extend(["--bundle", args.bundle])
            if args.root:
                forwarded.extend(["--root", args.root])
            if getattr(args, "skill_target", None):
                forwarded.extend(["--skill-target", args.skill_target])
            if getattr(args, "version", None):
                forwarded.extend(["--version", args.version])
            if getattr(args, "force_reinstall", False):
                forwarded.append("--force-reinstall")
            return manager_main([args.command, *forwarded])
    except BundleError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except (OSError, UnicodeError) as exc:
        print(
            f"ERROR: bundle I/O failure: {exc.__class__.__name__}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
