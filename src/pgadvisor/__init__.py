"""Slow-query log analysis and index suggestion for PostgreSQL."""

from .parser import LogEntry, parse_log, normalize_sql, fingerprint
from .extractor import QueryShape, extract_shape
from .advisor import Suggestion, advise, rank

__all__ = [
    "LogEntry", "parse_log", "normalize_sql", "fingerprint",
    "QueryShape", "extract_shape",
    "Suggestion", "advise", "rank",
]

__version__ = "0.1.0"
