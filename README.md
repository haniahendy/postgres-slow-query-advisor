# postgres-slow-query-advisor

Reads a PostgreSQL `log_min_duration_statement` slow-query log, aggregates
identical query shapes (literals folded), and proposes a ranked review list
of candidate btree indexes with `CREATE INDEX CONCURRENTLY` statements and
human-readable rationale.

Pure Python 3.10+, zero dependencies.

## Usage

```bash
PYTHONPATH=src python3 -m pgadvisor.cli slow.log --min-ms 100
```

```json
{
  "entries": 4,
  "unique_shapes": 3,
  "suggestions": [
    {
      "table": "orders",
      "columns": ["customer_id", "status", "created_at"],
      "reason": "2x slow queries, 792 ms total, predicate/ordering columns",
      "ddl": "CREATE INDEX CONCURRENTLY idx_orders_customer_id_status_created_at ON orders (customer_id, status, created_at);"
    }
  ]
}
```

## How it ranks

Each distinct query shape (SHA-256 of the normalized SQL, literals folded to
`?`, key truncated to 16 hex chars) accumulates count / total / max duration.
Suggestions are generated per table and only when that table's accumulated
slow time reaches `--min-ms`. They rank by total_ms, then count, so the worst
aggregate offenders come first, not the single slowest call.

## Honest limits

- **Not a SQL parser.** Table and column extraction is regex-based and
  correct for straightforward SELECT/WHERE/JOIN/GROUP BY/ORDER BY. CTEs,
  subqueries, functions in predicates and quoted mixed-case identifiers can
  produce wrong or missing columns. Read every suggestion before applying.
- No catalog statistics: it cannot know row counts, existing indexes, or
  selectivity, so column order is "equality first" heuristics, not cost-based.
- Aliases it cannot resolve fall back to the first table (documented in code).
- Suggestions are review items; validate with `EXPLAIN` before production.

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

8 tests: multi-entry parsing, literal-folding fingerprints, normalization,
shape extraction (aliased + bare columns), threshold gating, ranking, and a
CLI end-to-end pass over a sample log.
