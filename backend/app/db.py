from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


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


def migrate_sqlite() -> None:
    """Additive micro-migration: add any model columns missing from existing
    tables (SQLite `create_all` never alters tables that already exist)."""
    if not settings.database_url.startswith("sqlite"):
        return
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
                coltype = col.type.compile(engine.dialect)
                default = col.default.arg if col.default is not None and not callable(getattr(col.default, "arg", None)) else None
                ddl = f'ALTER TABLE {table.name} ADD COLUMN {col.name} {coltype}'
                if isinstance(default, str):
                    ddl += f" DEFAULT '{default}'"
                elif isinstance(default, (int, float, bool)):
                    ddl += f" DEFAULT {int(default) if isinstance(default, bool) else default}"
                conn.execute(text(ddl))
