"""Additive schema migration must work on the central tier's Postgres too.

The migration used to return early on any non-SQLite URL. Edge nodes (SQLite)
therefore picked up new columns on restart while the hosted central tier's
Postgres kept whatever schema it was first created with, so every SELECT of a
model that had gained a column raised UndefinedColumn — 500s on the registry,
vehicles and alert-episode endpoints while the identical code passed locally.
"""

import inspect as _inspect

from sqlalchemy import Boolean, Column, Float, Integer, String
from sqlalchemy.dialects import postgresql, sqlite

from app.db import add_column_ddl, migrate_schema

PG = postgresql.dialect()
LITE = sqlite.dialect()


def test_migration_is_not_gated_on_sqlite():
    """The regression guard: no dialect-based early return may come back."""
    src = _inspect.getsource(migrate_schema)
    assert 'startswith("sqlite")' not in src
    assert "return" not in src.split('"""')[2]  # no early return after the docstring


def test_string_column_ddl_on_both_dialects():
    col = Column("alt_rtsp_url", String, default="")
    for dialect in (PG, LITE):
        ddl = add_column_ddl("cameras", col, dialect)
        assert ddl.startswith("ALTER TABLE")
        assert "alt_rtsp_url" in ddl
        assert "DEFAULT ''" in ddl


def test_match_type_column_ddl_carries_its_default():
    """Alert.match_type is the column whose absence broke alert episodes."""
    col = Column("match_type", String, default="exact")
    assert "DEFAULT 'exact'" in add_column_ddl("alerts", col, PG)


def test_boolean_default_uses_dialect_appropriate_literal():
    """Postgres rejects 0/1 for a boolean; SQLite has no TRUE/FALSE keyword."""
    col = Column("monitoring", Boolean, default=True)
    assert "DEFAULT TRUE" in add_column_ddl("cameras", col, PG)
    assert "DEFAULT 1" in add_column_ddl("cameras", col, LITE)


def test_numeric_and_nullable_columns():
    assert "DEFAULT 0" in add_column_ddl("cameras", Column("bitrate_kbps", Integer, default=0), PG)
    # nullable, no default -> plain ADD COLUMN, safe on a populated table
    ddl = add_column_ddl("cameras", Column("source_fps", Float, nullable=True), PG)
    assert "DEFAULT" not in ddl


def test_string_default_is_escaped():
    """A quote in a default must not terminate the literal."""
    ddl = add_column_ddl("cameras", Column("note", String, default="it's live"), PG)
    assert "DEFAULT 'it''s live'" in ddl


def test_identifiers_are_quoted_when_they_need_it():
    """Plain lowercase names are left bare (valid SQL); a reserved word or
    mixed case must be quoted or the ALTER would be a syntax error."""
    plain = add_column_ddl("alerts", Column("match_type", String, default="exact"), PG)
    assert "ALTER TABLE alerts ADD COLUMN match_type" in plain

    reserved = add_column_ddl("alerts", Column("order", String, default=""), PG)
    assert '"order"' in reserved
