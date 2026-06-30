# policy_check/doc_drift/__main__.py
from __future__ import annotations

import argparse
import sys

from policy_check.doc_drift import engine


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="doc-drift")
    p.add_argument("--mode", choices=["doc-drift", "moc"], default="doc-drift")
    p.add_argument("--repo", default=".")
    p.add_argument("--base", required=True)
    p.add_argument("--head", default="HEAD")
    p.add_argument("--map", default="docs/MOC.md")
    p.add_argument("--governed-prefix", action="append", default=None, dest="prefixes")
    args = p.parse_args(argv)

    try:
        if args.mode == "doc-drift":
            fails, warns = engine.run_doc_drift(args.repo, args.base, args.head)
        else:
            prefixes = tuple(args.prefixes) if args.prefixes else None
            from policy_check.doc_drift.coverage import DEFAULT_GOVERNED_PREFIXES
            fails, warns = engine.run_moc(args.repo, args.base, args.map,
                                          prefixes or DEFAULT_GOVERNED_PREFIXES, args.head)
    except engine.DriftProvisionError as exc:
        # base/head 物件無法供給 → fail-fast，不靜默放行（doc-drift-core spec）
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    for line in fails:
        print(f"FAIL {line}")
    for line in warns:
        print(f"WARN {line}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
