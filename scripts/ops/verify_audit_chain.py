"""Verify audit_log hash chain integrity (ARCHITECTURE_REVIEW §B-3 / §E.3).

Run as a daily CronJob; exit non-zero on any broken link so the Prometheus
Job / K8s monitoring flags it.

Usage:
    python scripts/ops/verify_audit_chain.py              # report & exit
    python scripts/ops/verify_audit_chain.py --quiet      # exit code only
"""

from __future__ import annotations

import argparse
import asyncio
import sys


async def _main() -> int:
    ap = argparse.ArgumentParser(description="Verify audit_log hash chain")
    ap.add_argument("--quiet", action="store_true", help="print nothing; exit code only")
    ap.add_argument("--batch-size", type=int, default=1000)
    args = ap.parse_args()

    from sia.common.audit import verify_chain  # noqa: WPS433 — late import

    checked, broken = await verify_chain(batch_size=args.batch_size)

    if not args.quiet:
        print(f"audit_log rows checked: {checked}")
        if broken:
            print(f"BROKEN CHAIN at rows: {broken[:50]}"
                  + (" …" if len(broken) > 50 else ""))
        else:
            print("chain OK")

    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
