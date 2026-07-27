from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from core.config import settings


class Base(DeclarativeBase):
    pass


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    from database import models  # noqa: F401
    from database.seed import seed_demo_data

    Base.metadata.create_all(bind=engine)
    ensure_runtime_indexes()
    ensure_runtime_columns()
    with SessionLocal() as db:
        seed_demo_data(db)


def ensure_runtime_indexes() -> None:
    if engine.dialect.name not in {"sqlite", "postgresql"}:
        return

    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ix_approvals_one_pending_per_document
            ON approvals (document_id)
            WHERE status = 'pending'
            """
        )


def ensure_runtime_columns() -> None:
    if engine.dialect.name == "sqlite":
        with engine.begin() as connection:
            rows = connection.exec_driver_sql("PRAGMA table_info('documents')").mappings().all()
            columns = {row["name"] for row in rows}
            if "summary" not in columns:
                connection.exec_driver_sql("ALTER TABLE documents ADD COLUMN summary TEXT NOT NULL DEFAULT ''")
        return

    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE documents ADD COLUMN IF NOT EXISTS summary TEXT NOT NULL DEFAULT ''")
