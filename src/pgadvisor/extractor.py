"""Extract a rough relational shape from a SELECT statement.

This is deliberately not a SQL parser: it reads FROM/JOIN tables and the
columns named in WHERE / JOIN ... ON / GROUP BY / ORDER BY. It is wrong on
subqueries, CTEs and quoted identifiers in the general case; the advisor's
output is a review list for a human, not DDL to apply blindly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_TABLE_RE = re.compile(r"\b(?:from|join)\s+([a-z_][\w.]*)", re.IGNORECASE)
_ALIAS_RE = re.compile(r"\b(?:from|join)\s+[a-z_][\w.]*\s+(?:as\s+)?([a-z_]\w*)", re.IGNORECASE)
_PRED_RE = re.compile(r"\b([a-z_]\w*)\.([a-z_]\w*)\s*(?:=|<|>|<=|>=|<>|!=|\blike\b|\bin\b)(?=[\s?])", re.IGNORECASE)
_WHERE_RE = re.compile(r"\bwhere\s+(.+?)(?:\bgroup\s+by\b|\border\s+by\b|\blimit\b|$)", re.IGNORECASE)
_BARE_RE = re.compile(r"(?<![.\w])([a-z_]\w*)\s*(?:=|<>|!=|<=|>=|<|>|\blike\b|\bin\b)", re.IGNORECASE)
_SKIP = {"and", "or", "not", "null", "in", "like", "is", "where", "on", "select", "case", "then", "else", "end"}
_GROUP_RE = re.compile(r"\bgroup\s+by\s+([^;]+?)(?:\border\s+by\b|\blimit\b|$)", re.IGNORECASE)
_ORDER_RE = re.compile(r"\border\s+by\s+([^;]+?)(?:\blimit\b|$)", re.IGNORECASE)


@dataclass
class QueryShape:
    tables: list[str] = field(default_factory=list)
    where_columns: list[tuple[str, str]] = field(default_factory=list)  # (table_or_alias, column)
    group_columns: list[str] = field(default_factory=list)
    order_columns: list[str] = field(default_factory=list)


def _split_cols(blob: str) -> list[str]:
    cols = []
    for part in blob.split(","):
        part = re.sub(r"\b(asc|desc|nulls\s+(?:first|last))\b", "", part.strip(), flags=re.I).strip()
        if part and "(" not in part:
            cols.append(part)
    return cols


def extract_shape(normalized_sql: str) -> QueryShape:
    shape = QueryShape()
    shape.tables = [t.split(".")[-1] for t in _TABLE_RE.findall(normalized_sql)]
    shape.where_columns = [(a, c) for a, c in _PRED_RE.findall(normalized_sql)]
    w = _WHERE_RE.search(normalized_sql)
    if w:
        for col in _BARE_RE.findall(w.group(1)):
            if col not in _SKIP and all(c != col for _, c in shape.where_columns):
                shape.where_columns.append(("", col))
    g = _GROUP_RE.search(normalized_sql)
    if g:
        shape.group_columns = _split_cols(g.group(1))
    o = _ORDER_RE.search(normalized_sql)
    if o:
        shape.order_columns = _split_cols(o.group(1))
    return shape
