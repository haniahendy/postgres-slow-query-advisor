"""CLI: python -m pgadvisor.cli slow.log [--min-ms 100]"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict

from .parser import parse_log
from .extractor import extract_shape
from .advisor import advise, rank


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Suggest indexes from a Postgres slow-query log")
    ap.add_argument("logfile")
    ap.add_argument("--min-ms", type=float, default=100.0)
    args = ap.parse_args(argv)

    entries = parse_log(open(args.logfile, encoding="utf-8").read())
    if not entries:
        print("no duration entries found", file=sys.stderr)
        return 1

    stats = defaultdict(lambda: {"count": 0, "total_ms": 0.0, "max_ms": 0.0, "sql": ""})
    for e in entries:
        s = stats[e.fingerprint]
        s["count"] += 1
        s["total_ms"] += e.duration_ms
        s["max_ms"] = max(s["max_ms"], e.duration_ms)
        s["sql"] = e.normalized

    suggestions = []
    for s in stats.values():
        shape = extract_shape(s["sql"])
        suggestions += advise(shape, total_ms=s["total_ms"], query_count=s["count"],
                              min_total_ms=args.min_ms)
    report = {
        "entries": len(entries),
        "unique_shapes": len(stats),
        "suggestions": [vars(x) for x in rank(suggestions)],
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
