from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
from sqlalchemy import Column, Integer, String, DateTime, create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

DB_DATA_DIR = os.getenv("DB_PATH", os.getenv("DATA_DIR", "."))
Path(DB_DATA_DIR).mkdir(parents=True, exist_ok=True)

DEFAULT_DB_FILE = os.path.join(DB_DATA_DIR, "shorturl.db")
SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL", f"sqlite:///{DEFAULT_DB_FILE}"
)

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

DEFAULT_RETENTION_DAYS = 365


def default_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=DEFAULT_RETENTION_DAYS)


class ShortURL(Base):
    __tablename__ = "short_urls"

    id = Column(Integer, primary_key=True, index=True)
    short_code = Column(String(64), unique=True, index=True, nullable=False)
    original_url = Column(String(2048), nullable=False)
    custom_description = Column(String(2048), nullable=True)
    clicks = Column(Integer, default=0, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    expires_at = Column(
        DateTime(timezone=True),
        default=default_expires_at,
        nullable=True,
    )
    meta_title = Column(String(512), nullable=True)
    meta_description = Column(String(2048), nullable=True)
    meta_image = Column(String(2048), nullable=True)
    favicon_url = Column(String(2048), nullable=True)
    meta_updated_at = Column(DateTime(timezone=True), nullable=True)


def init_db():
    Base.metadata.create_all(bind=engine)
    # Migrate existing SQLite table if columns were added after initial creation
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(short_urls)")).fetchall()
        existing_cols = {row[1] for row in rows}
        migrations = [
            ("custom_description", "VARCHAR(2048)"),
            ("meta_title", "VARCHAR(512)"),
            ("meta_description", "VARCHAR(2048)"),
            ("meta_image", "VARCHAR(2048)"),
            ("favicon_url", "VARCHAR(2048)"),
            ("meta_updated_at", "DATETIME"),
        ]
        for col_name, col_type in migrations:
            if col_name not in existing_cols:
                conn.execute(
                    text(f"ALTER TABLE short_urls ADD COLUMN {col_name} {col_type}")
                )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
