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
    args = p.parse_args(argv)

    if args.mode == "doc-drift":
        fails, warns = engine.run_doc_drift(args.repo, args.base, args.head)
    else:
        fails, warns = [], []  # moc mode 於 Task 後續接 coverage（P2 充實）
    for line in fails:
        print(f"FAIL {line}")
    for line in warns:
        print(f"WARN {line}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
