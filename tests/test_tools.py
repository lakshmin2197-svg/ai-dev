import sqlite3
import unittest

from tools import load_programs_db, query_data


class TestQueryData(unittest.TestCase):
    def setUp(self):
        self.con = load_programs_db()

    def test_simple_select_returns_rows(self):
        rows = query_data("SELECT COUNT(*) FROM programs", self.con)
        self.assertEqual(rows, [[150]])

    def test_select_with_where_clause(self):
        rows = query_data(
            "SELECT COUNT(*) FROM programs WHERE sector = 'education'", self.con
        )
        self.assertEqual(rows[0][0], 50)

    def test_trailing_semicolon_is_tolerated(self):
        rows = query_data("SELECT COUNT(*) FROM programs;", self.con)
        self.assertEqual(rows, [[150]])

    def test_rejects_non_string_sql(self):
        with self.assertRaises(ValueError):
            query_data(None, self.con)

    def test_rejects_empty_sql(self):
        with self.assertRaises(ValueError):
            query_data("   ", self.con)

    def test_rejects_non_select_statement(self):
        with self.assertRaises(ValueError):
            query_data("DELETE FROM programs", self.con)

    def test_rejects_drop_table(self):
        with self.assertRaises(ValueError):
            query_data("DROP TABLE programs", self.con)

    def test_rejects_chained_statements(self):
        with self.assertRaises(ValueError):
            query_data("SELECT * FROM programs; DROP TABLE programs", self.con)

    def test_rejects_pragma(self):
        with self.assertRaises(ValueError):
            query_data("PRAGMA table_info(programs)", self.con)

    def test_bad_sql_syntax_raises_value_error_not_crash(self):
        with self.assertRaises(ValueError):
            query_data("SELECT FROM WHERE", self.con)

    def test_unknown_column_raises_value_error_not_crash(self):
        with self.assertRaises(ValueError):
            query_data("SELECT nonexistent_column FROM programs", self.con)

    def test_data_survives_a_blocked_attack(self):
        try:
            query_data("DROP TABLE programs", self.con)
        except ValueError:
            pass
        rows = query_data("SELECT COUNT(*) FROM programs", self.con)
        self.assertEqual(rows, [[150]])

    def test_aggregate_queries_are_unaffected_by_the_column_allowlist(self):
        rows = query_data("SELECT COUNT(*) FROM programs", self.con)
        self.assertEqual(rows, [[150]])
        rows = query_data("SELECT AVG(budget_usd) FROM programs", self.con)
        self.assertEqual(len(rows), 1)

    def test_column_allowlist_blocks_a_sensitive_column_not_in_the_schema_it_was_built_for(self):
        con = sqlite3.connect(":memory:")
        con.execute("CREATE TABLE programs (program_id TEXT, program_name TEXT, ssn TEXT)")
        con.execute("INSERT INTO programs VALUES ('P001', 'Test Program', '123-45-6789')")

        with self.assertRaises(ValueError):
            query_data("SELECT ssn FROM programs", con)
        with self.assertRaises(ValueError):
            query_data("SELECT * FROM programs", con)

        rows = query_data("SELECT program_id FROM programs", con)
        self.assertEqual(rows, [["P001"]])

    def test_keyword_blocklist_can_false_positive_on_literal_text(self):
        with self.assertRaises(ValueError):
            query_data(
                "SELECT * FROM programs WHERE program_name = 'Water Drop Project'",
                self.con,
            )


if __name__ == "__main__":
    unittest.main()
