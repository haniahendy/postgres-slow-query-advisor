"""Turn query shapes + usage statistics into ranked index suggestions.

Rules (deliberately conservative):
- equality/range predicates on the same table -> btree on those columns,
  equality columns first;
- GROUP BY / ORDER BY columns appended if not already covered;
- a table needs total_ms >= min_total_ms before anything is suggested.

Ranking: total_ms desc, then query count desc. The output is a review list
with human-readable rationale, not migrations.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .extractor import QueryShape

_KEYWORDS = {"where", "on", "and", "or", "join", "select", "group", "order"}


@dataclass
class Suggestion:
    table: str
    columns: list[str]
    reason: str
    total_ms: float
    query_count: int
    ddl: str


def _resolve(alias_or_table: str, shape: QueryShape) -> str | None:
    if alias_or_table in shape.tables:
        return alias_or_table
    if len(shape.tables) == 1:
        return shape.tables[0]
    if alias_or_table in _KEYWORDS:
        return None
    # assume alias of first table when unresolvable (documented limitation)
    return shape.tables[0] if shape.tables else None


def advise(shape: QueryShape, *, total_ms: float, query_count: int,
           min_total_ms: float = 100.0) -> list[Suggestion]:
    if not shape.tables or total_ms < min_total_ms:
        return []
    by_table: dict[str, list[str]] = {}
    for alias, col in shape.where_columns:
        t = _resolve(alias, shape)
        if t and col not in by_table.setdefault(t, []):
            by_table[t].append(col)
    for col in shape.group_columns + shape.order_columns:
        t = shape.tables[0]
        bare = col.split(".")[-1]
        if t and bare not in by_table.setdefault(t, []):
            by_table[t].append(bare)
    out = []
    for table, cols in by_table.items():
        idx = f"idx_{table}_{'_'.join(cols[:4])}"
        out.append(Suggestion(
            table=table,
            columns=cols,
            reason=f"{query_count}x slow queries, {total_ms:.0f} ms total, predicate/ordering columns",
            total_ms=total_ms,
            query_count=query_count,
            ddl=f'CREATE INDEX CONCURRENTLY {idx} ON {table} ({", ".join(cols)});',
        ))
    return out


def rank(suggestions: list[Suggestion]) -> list[Suggestion]:
    return sorted(suggestions, key=lambda s: (-s.total_ms, -s.query_count))
