"""Database tables and session handling (SQLAlchemy 2).

SQLite is used locally and works out of the box. For persistent cloud storage set
DATABASE_URL to a Postgres URL (e.g. a free Neon or Supabase database).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import DateTime, Integer, LargeBinary, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.config import get_settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class ProjectRow(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(120))
    is_demo: Mapped[bool] = mapped_column(default=False)
    data: Mapped[str] = mapped_column(Text)  # ProjectData as JSON
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ImageRow(Base):
    __tablename__ = "images"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(64), index=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    jpeg: Mapped[bytes] = mapped_column(LargeBinary)
    quality: Mapped[str] = mapped_column(Text)  # QualityReport as JSON
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AnalysisCacheRow(Base):
    """AI results keyed by image hash: re-analysing the same photo costs no API quota."""

    __tablename__ = "analysis_cache"

    sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    result: Mapped[str] = mapped_column(Text)  # AnalysisResult as JSON
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


def _normalise_url(url: str) -> str:
    # Hosted Postgres providers hand out postgres:// URLs; SQLAlchemy needs the driver name.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def _make_engine():
    url = _normalise_url(get_settings().database_url)
    if url.startswith("sqlite:///"):
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url, pool_pre_ping=True)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
