from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings
import os
import sqlite3

db_path = settings.database_url.replace("sqlite:///", "")
db_dir = os.path.dirname(db_path)
if db_dir and not os.path.exists(db_dir):
    os.makedirs(db_dir, exist_ok=True)

connect_args = {}
is_sqlite = settings.database_url.startswith("sqlite")
if is_sqlite:
    connect_args["check_same_thread"] = False
    connect_args["timeout"] = 30

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=30,
    pool_timeout=30,
    future=True,
)


def _sqlite_on_connect(dbapi_con, connection_record):
    if isinstance(dbapi_con, sqlite3.Connection):
        dbapi_con.execute("PRAGMA journal_mode=WAL")
        dbapi_con.execute("PRAGMA synchronous=NORMAL")
        dbapi_con.execute("PRAGMA busy_timeout=30000")
        dbapi_con.execute("PRAGMA cache_size=-64000")


if is_sqlite:
    event.listen(engine, "connect", _sqlite_on_connect)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
