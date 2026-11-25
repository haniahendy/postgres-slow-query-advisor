import json
import unittest

from pgadvisor import parse_log, normalize_sql, extract_shape, advise, rank
from pgadvisor.cli import main

SAMPLE_LOG = """2026-11-25 03:12:44 UTC [1234] LOG:  duration: 412.317 ms  statement: SELECT * FROM orders WHERE customer_id = 4812 AND status = 'open' ORDER BY created_at DESC;
2026-11-25 03:13:01 UTC [1234] LOG:  duration: 380.102 ms  statement: SELECT * FROM orders WHERE customer_id = 922 AND status = 'open' ORDER BY created_at DESC;
2026-11-25 03:14:20 UTC [1234] LOG:  duration: 12.004 ms  statement: SELECT id, name FROM customers WHERE id = 7;
2026-11-25 03:15:40 UTC [1234] LOG:  duration: 250.500 ms  statement: SELECT p.title, c.name FROM products p JOIN categories c ON c.id = p.category_id WHERE c.slug = 'audio' AND p.price < 200;
"""


class TestParser(unittest.TestCase):
    def test_parses_all_entries(self):
        self.assertEqual(len(parse_log(SAMPLE_LOG)), 4)

    def test_literal_folding_fingerprints(self):
        entries = parse_log(SAMPLE_LOG)
        self.assertEqual(entries[0].fingerprint, entries[1].fingerprint)
        self.assertNotEqual(entries[0].fingerprint, entries[2].fingerprint)

    def test_normalize(self):
        self.assertEqual(
            normalize_sql("SELECT * FROM t WHERE a = 42 AND b = 'x y';"),
            "select * from t where a = ? and b = ?",
        )


class TestShape(unittest.TestCase):
    def test_tables_and_columns(self):
        entries = parse_log(SAMPLE_LOG)
        shape = extract_shape(entries[3].normalized)
        self.assertEqual(shape.tables, ["products", "categories"])
        cols = {c for _, c in shape.where_columns}
        self.assertIn("slug", cols)
        self.assertIn("price", cols)


class TestAdvisor(unittest.TestCase):
    def test_suggestion_for_hot_shape(self):
        entries = parse_log(SAMPLE_LOG)
        shape = extract_shape(entries[0].normalized)
        sugg = advise(shape, total_ms=792.4, query_count=2)
        self.assertEqual(len(sugg), 1)
        self.assertEqual(sugg[0].table, "orders")
        self.assertIn("customer_id", sugg[0].columns)
        self.assertIn("CREATE INDEX CONCURRENTLY", sugg[0].ddl)

    def test_below_threshold_no_suggestion(self):
        entries = parse_log(SAMPLE_LOG)
        shape = extract_shape(entries[2].normalized)
        self.assertEqual(advise(shape, total_ms=12.0, query_count=1), [])

    def test_rank_order(self):
        entries = parse_log(SAMPLE_LOG)
        s1 = advise(extract_shape(entries[0].normalized), total_ms=792.4, query_count=2)
        s2 = advise(extract_shape(entries[3].normalized), total_ms=250.5, query_count=1)
        ranked = rank(s1 + s2)
        self.assertEqual(ranked[0].table, "orders")


class TestCli(unittest.TestCase):
    def test_cli_end_to_end(self):
        import io, contextlib, tempfile, os
        with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as f:
            f.write(SAMPLE_LOG)
            path = f.name
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main([path, "--min-ms", "100"])
        os.unlink(path)
        self.assertEqual(rc, 0)
        report = json.loads(buf.getvalue())
        self.assertEqual(report["entries"], 4)
        self.assertEqual(report["unique_shapes"], 3)
        self.assertGreaterEqual(len(report["suggestions"]), 1)


if __name__ == "__main__":
    unittest.main()
