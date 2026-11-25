"""split_statements contract: PostgreSQL lexing rules decide where statements end.

Pinned because a v116 -- comment containing a semicolon once split mid-comment
and a fresh migrate executed the comment prose as SQL (syntax error at "the").
The splitter must protect semicolons inside strings, identifiers, dollar
quotes, line comments and block comments, and still split the real boundaries.
"""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('mizan_migrations', ROOT / 'app/db/migrations.py')
migrations = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migrations)
split = migrations.split_statements


class SplitStatementsTest(unittest.TestCase):
    def test_plain_boundaries_split(self):
        self.assertEqual(split('SELECT 1; SELECT 2;'), ['SELECT 1', 'SELECT 2'])
        self.assertEqual(split('SELECT 1'), ['SELECT 1'])
        self.assertEqual(split(';;'), [])

    def test_semicolon_inside_single_quoted_string_never_splits(self):
        self.assertEqual(
            split("INSERT INTO t VALUES ('a;b'); SELECT 2;"),
            ["INSERT INTO t VALUES ('a;b')", 'SELECT 2'])
        # '' escape keeps the string open; the ; after it is still inside.
        self.assertEqual(
            split("SELECT 'it''s;fine'; SELECT 2;"),
            ["SELECT 'it''s;fine'", 'SELECT 2'])

    def test_semicolon_inside_quoted_identifier_never_splits(self):
        self.assertEqual(
            split('CREATE TABLE "a;b" (id int); SELECT 2;'),
            ['CREATE TABLE "a;b" (id int)', 'SELECT 2'])

    def test_dollar_quoted_block_stays_one_statement(self):
        body = "DO $$\nBEGIN\n  EXECUTE 'ALTER TABLE x ENABLE ROW LEVEL SECURITY;';\nEND\n$$;"
        self.assertEqual(split(body + '\nSELECT 2;'), [body[:-1], 'SELECT 2'])
        tagged = "DO $body$ SELECT 1; $body$; SELECT 2;"
        self.assertEqual(split(tagged), ["DO $body$ SELECT 1; $body$", 'SELECT 2'])

    def test_line_comment_semicolon_never_splits(self):
        # The v116 regression: prose after a ; inside a -- comment must not execute.
        sql = "-- behaves identically); the table is retained\nCREATE TABLE t (id int);\nSELECT 2;"
        stmts = split(sql)
        self.assertEqual(len(stmts), 2)
        self.assertTrue(stmts[0].startswith('-- behaves identically'))
        self.assertIn('CREATE TABLE t', stmts[0])
        self.assertEqual(stmts[1], 'SELECT 2')

    def test_block_comment_semicolon_never_splits(self):
        self.assertEqual(
            split('/* keep; together */ SELECT 1; SELECT 2;'),
            ['/* keep; together */ SELECT 1', 'SELECT 2'])
        # PostgreSQL nests block comments.
        self.assertEqual(
            split('/* outer /* inner; */ still comment; */ SELECT 1;'),
            ['/* outer /* inner; */ still comment; */ SELECT 1'])

    def test_comment_syntax_inside_string_is_content(self):
        self.assertEqual(
            split("SELECT '--not;a comment'; SELECT 2;"),
            ["SELECT '--not;a comment'", 'SELECT 2'])
        self.assertEqual(
            split("SELECT '/*not;a comment*/'; SELECT 2;"),
            ["SELECT '/*not;a comment*/'", 'SELECT 2'])

    def test_quote_inside_comment_stays_comment(self):
        self.assertEqual(
            split("-- it's fine; really\nSELECT 1;"),
            ["-- it's fine; really\nSELECT 1"])

    def test_every_shipped_sql_migration_splits_without_prose_leak(self):
        # Replay guard: no statement may begin with lowercase English prose, the
        # exact v116 failure shape, and every migration must split into statements.
        import re as _re
        checked = 0
        for mid, sql in migrations.MIGRATIONS:
            if sql.startswith('python:'):
                continue
            checked += 1
            stmts = split(sql)
            self.assertTrue(stmts, mid)
            for stmt in stmts:
                first = _re.sub(r'^(--[^\n]*\n|/\*.*?\*/\s*|\s)+', '', stmt, flags=_re.S)
                self.assertNotRegex(first[:12].lower(), r'^(the |a |an |per |and |so )', f'{mid}: {stmt[:80]}')
        self.assertGreater(checked, 100)


if __name__ == '__main__':
    unittest.main()
