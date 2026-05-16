from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)


def _sqlite_add_missing_columns() -> None:
    """
    Minimal dev-friendly migration for SQLite.
    SQLModel/SQLAlchemy `create_all` does not add columns to existing tables.
    """
    if not settings.database_url.startswith("sqlite"):
        return

    with engine.connect() as conn:
        # User table columns
        rows = conn.exec_driver_sql("PRAGMA table_info('user')").fetchall()
        existing = {r[1] for r in rows}  # column name at index 1
        desired_user = {
            "last_login_at": "DATETIME",
            "password_hash": "TEXT",
            "terms_accepted_at": "DATETIME",
        }
        for col, col_type in desired_user.items():
            if col not in existing:
                conn.exec_driver_sql(f"ALTER TABLE user ADD COLUMN {col} {col_type}")
        
        # Trade table columns
        trade_rows = conn.exec_driver_sql("PRAGMA table_info('trade')").fetchall()
        trade_existing = {r[1] for r in trade_rows}
        desired_trade = {
            "exit_price": "REAL",
            "exit_at": "DATETIME",
            "status": "TEXT DEFAULT 'active'",
            "cancelled_at": "DATETIME",
            "cancelled_reason": "TEXT",
        }
        for col, col_type in desired_trade.items():
            if col not in trade_existing:
                conn.exec_driver_sql(f"ALTER TABLE trade ADD COLUMN {col} {col_type}")
        
        conn.commit()


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    _sqlite_add_missing_columns()


def get_session():
    with Session(engine) as session:
        yield session

