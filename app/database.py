from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

db_url = settings.database_url
# SQLAlchemy 2.1 changed "postgresql://" to default to psycopg (v3), but this
# project installs psycopg2-binary. Naming the driver explicitly works on every
# SQLAlchemy version, so a fresh deploy can't break on the connection string
# (it also fixes "postgres://" URLs, which SQLAlchemy has never accepted).
if db_url.startswith("postgres://"):
    db_url = "postgresql+psycopg2://" + db_url[len("postgres://"):]
elif db_url.startswith("postgresql://"):
    db_url = "postgresql+psycopg2://" + db_url[len("postgresql://"):]

connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
engine = create_engine(db_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
