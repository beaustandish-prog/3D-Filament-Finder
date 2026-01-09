import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# Use environment variable for production (PostgreSQL), fallback to local SQLite
DATABASE_URL = os.getenv("DATABASE_URL")

# Vercel-specific check: They must have a DATABASE_URL set
if os.getenv("VERCEL") and not DATABASE_URL:
    print("CRITICAL: DATABASE_URL not found in Vercel environment!")
    # We can't use SQLite on Vercel's read-only filesystem, so we must error out
    # or the app will crash with an obscure 'sqlite3.OperationalError' later.
    raise ValueError("DATABASE_URL is required for Vercel deployment.")

if not DATABASE_URL:
    # Local development fallback
    DATABASE_URL = "sqlite:///./filament_minder.db"
    print(f"Connecting to local SQLite database: {DATABASE_URL}")
else:
    print(f"Connecting to hosted database (Type: {'PostgreSQL' if 'post' in DATABASE_URL else 'Other'})")

# Handle PostgreSQL prefix compatibility for SQLAlchemy 1.4+
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# SQLite-specific connect_args
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
