from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from .config import settings

# Ensure the directory for the SQLite database file exists before the engine
# tries to create it.  Only applies to file-based sqlite:/// URLs.
_db_url = settings.database_url
if _db_url.startswith("sqlite:///"):
    _db_file = Path(_db_url[len("sqlite:///"):])
    if not _db_file.is_absolute():
        _db_file = Path.cwd() / _db_file
    _db_file.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    future=True,
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
Base = declarative_base()

class Song(Base):
    __tablename__ = "songs"

    id = Column(Integer, primary_key=True, index=True)
    artist = Column(String, nullable=False)
    title = Column(String, nullable=False)
    album = Column(String, nullable=True)
    musicbrainz_id = Column(String, nullable=True)
    acoustid_id = Column(String, nullable=True)
    first_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    plays = relationship("Play", back_populates="song", cascade="all, delete-orphan")

class Play(Base):
    __tablename__ = "plays"

    id = Column(Integer, primary_key=True, index=True)
    song_id = Column(Integer, ForeignKey("songs.id"), nullable=False)
    station_name = Column(String, nullable=False)
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    confidence = Column(Float, nullable=False)
    provider = Column(String, nullable=False)
    raw_result_json = Column(Text, nullable=False)

    song = relationship("Song", back_populates="plays")

class Station(Base):
    __tablename__ = "stations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    stream_url = Column(String, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
