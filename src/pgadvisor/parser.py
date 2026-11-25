"""Parse PostgreSQL slow-query logs into normalized, fingerprinted entries.

Handles the common `log_min_duration_statement` format:
    2026-11-25 03:12:44 UTC [1234] LOG:  duration: 42.317 ms  statement: SELECT ...
Multi-line statements are folded. Literals are replaced with '?' before
fingerprinting so the same query shape aggregates regardless of parameters.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

_DURATION_RE = re.compile(
    r"duration:\s*([\d.]+)\s*ms\s+(?:statement|execute\s+\S+):\s*(.*?)(?=\s+\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}|\s*$)",
    re.IGNORECASE | re.DOTALL,
)
_STR_RE = re.compile(r"'(?:[^']|'')*'")
_NUM_RE = re.compile(r"\b\d+(?:\.\d+)?\b")
_WS_RE = re.compile(r"\s+")


@dataclass
class LogEntry:
    duration_ms: float
    statement: str
    normalized: str = field(init=False)
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        self.normalized = normalize_sql(self.statement)
        self.fingerprint = fingerprint(self.normalized)


def normalize_sql(sql: str) -> str:
    """Lowercase, strip literals/numbers, collapse whitespace."""
    out = sql.strip().rstrip(";").lower()
    out = _STR_RE.sub("?", out)
    out = _NUM_RE.sub("?", out)
    out = out.replace('"', "")
    return _WS_RE.sub(" ", out).strip()


def fingerprint(normalized: str) -> str:
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def parse_log(text: str) -> list[LogEntry]:
    """Extract duration+statement pairs from log text.

    Lines that do not match the duration marker are ignored; multi-line
    statements are re-joined by collapsing the log into one string first.
    """
    joined = _WS_RE.sub(" ", text)
    return [
        LogEntry(duration_ms=float(m.group(1)), statement=m.group(2).strip())
        for m in _DURATION_RE.finditer(joined)
    ]
