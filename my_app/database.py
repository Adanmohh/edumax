# my_app/database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from .config import DATABASE_URL

import sys

import os

# Extract database file path from URL
db_path = DATABASE_URL.replace('sqlite:///', '')
print(f"Debug: Database file path: {db_path}", file=sys.stderr)

# Check if database file exists
if os.path.exists(db_path):
    print(f"Debug: Database file exists at {db_path}", file=sys.stderr)
    print(f"Debug: File size: {os.path.getsize(db_path)} bytes", file=sys.stderr)
    print(f"Debug: File permissions: {oct(os.stat(db_path).st_mode)}", file=sys.stderr)
else:
    print(f"Debug: Database file does not exist at {db_path}", file=sys.stderr)
    print(f"Debug: Parent directory exists: {os.path.exists(os.path.dirname(db_path))}", file=sys.stderr)
    print(f"Debug: Parent directory writable: {os.access(os.path.dirname(db_path), os.W_OK)}", file=sys.stderr)

print(f"Debug: Creating database engine with URL: {DATABASE_URL}", file=sys.stderr)
try:
    engine = create_engine(
        DATABASE_URL, 
        connect_args={"check_same_thread": False},
        echo=True,  # Enable SQL logging
        echo_pool=True  # Enable connection pool logging
    )
    print("Debug: Database engine created successfully", file=sys.stderr)
    
    # Test connection
    from sqlalchemy import text
    with engine.connect() as conn:
        print("Debug: Successfully connected to database", file=sys.stderr)
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
        print(f"Debug: Tables in database: {[r[0] for r in result]}", file=sys.stderr)
except Exception as e:
    print(f"Debug: Error creating database engine: {str(e)}", file=sys.stderr)
    import traceback
    print(f"Debug: Engine error traceback: {traceback.format_exc()}", file=sys.stderr)
    raise
SessionLocal = sessionmaker(
    bind=engine, 
    autoflush=False, 
    autocommit=False,
    expire_on_commit=False  # Prevent detached instance errors
)
Base = declarative_base()

import sys

def get_db():
    db = None
    try:
        print("Debug: Creating new database session", file=sys.stderr)
        db = SessionLocal()
        print("Debug: Database session created successfully", file=sys.stderr)
        
        print("Debug: Enabling foreign key support", file=sys.stderr)
        db.execute(text("PRAGMA foreign_keys=ON"))
        print("Debug: Foreign key support enabled", file=sys.stderr)
        
        # Debug: Check database connection and tables
        print("Debug: Testing database connection", file=sys.stderr)
        result = db.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
        print(f"Debug: Available tables: {[r[0] for r in result]}", file=sys.stderr)
        
        yield db
    except Exception as e:
        print(f"Debug: Database error in get_db: {str(e)}", file=sys.stderr)
        import traceback
        print(f"Debug: Database error traceback: {traceback.format_exc()}", file=sys.stderr)
        raise
    finally:
        if db:
            print("Debug: Closing database session", file=sys.stderr)
            db.close()
            print("Debug: Database session closed", file=sys.stderr)
