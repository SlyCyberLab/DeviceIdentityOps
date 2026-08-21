"""
SQLite engine + session setup.

DATABASE_URL comes from .env (see .env.example) and defaults to a local
SQLite file if not set. get_db() is a FastAPI dependency - each request
gets its own session, which is closed automatically when the request ends.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./deviceidentityops.db")

# check_same_thread=False is needed for SQLite specifically, since FastAPI
# can use a different thread per request.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
