"""
SQLAlchemy Engine & Session Configuration

"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
# Load environment variables from .env 
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("❌ ไม่พบ DATABASE_URL ในไฟล์ .env! กรุณาเพิ่มก่อนเริ่มระบบ")
# Engine — manages the actual DBAPI connections to PostgreSQL
# pool_pre_ping=True ensures stale connections are recycled automatically.
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
# SessionLocal — factory that produces new Session objects.
# autocommit=False & autoflush=False give us explicit control over
# when data is written and committed to the database.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# Base — every ORM model will subclass this so SQLAlchemy can track them.
Base = declarative_base()
def get_db():
    """
    FastAPI dependency that provides a database session per request.

    Usage in a route:
        @app.get("/users")
        def list_users(db: Session = Depends(get_db)):
            ...

    The `finally` block guarantees the session is closed even if an
    exception occurs, preventing connection leaks.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
