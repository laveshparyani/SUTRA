import logging

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

log = logging.getLogger("sutra.db")


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)

if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def migrate_schema() -> None:
    """Additive micro-migration: add any model columns missing from existing
    tables. `create_all` creates missing tables but never alters existing ones,
    on any dialect.

    This deliberately runs on Postgres as well as SQLite. It was SQLite-only,
    which silently split the deployment in two: an edge node picked up every new
    column on restart while the central tier's Postgres kept the schema it was
    first created with. Columns added later (camera resolution/alt URLs,
    Alert.match_type) therefore existed only in the model, and every SELECT of a
    full model object raised UndefinedColumn — the registry, vehicles and alert
    episodes all returned 500 on the hosted tier while passing locally.

    Added columns are nullable with a default, so this is safe on a populated
    table and a no-op once applied.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing:
                    continue
                log.info("migrating %s: adding column %s", table.name, col.name)
                conn.execute(text(add_column_ddl(table.name, col, engine.dialect)))


def add_column_ddl(table_name, col, dialect) -> str:
    """Build one ADD COLUMN statement for the given dialect.

    Separated from the executor so it can be checked against the Postgres
    dialect without a Postgres server — the split between edge (SQLite) and
    central (Postgres) is exactly where this went wrong before.
    """
    preparer = dialect.identifier_preparer
    coltype = col.type.compile(dialect)
    raw = col.default.arg if col.default is not None and not callable(getattr(col.default, "arg", None)) else None
    ddl = f"ALTER TABLE {preparer.quote(table_name)} ADD COLUMN {preparer.quote(col.name)} {coltype}"
    if isinstance(raw, bool):
        # SQLite has no boolean literal; Postgres rejects 0/1 for one
        ddl += f" DEFAULT {('TRUE' if raw else 'FALSE') if dialect.name != 'sqlite' else int(raw)}"
    elif isinstance(raw, (int, float)):
        ddl += f" DEFAULT {raw}"
    elif isinstance(raw, str):
        ddl += " DEFAULT " + "'" + raw.replace("'", "''") + "'"
    return ddl


# kept so an older import path does not break mid-deploy
migrate_sqlite = migrate_schema
