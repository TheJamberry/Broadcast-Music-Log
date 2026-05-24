import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func

from .config import settings
from .db import Play, SessionLocal, Song, Station
from .detector import (
    build_song_key,
    capture_audio,
    fingerprint_audio,
    query_acoustid,
)

logger = logging.getLogger(__name__)


def get_existing_song(session, artist: str, title: str) -> Optional[Song]:
    normalized_artist = artist.strip().lower()
    normalized_title = title.strip().lower()
    return (
        session.query(Song)
        .filter(func.lower(Song.artist) == normalized_artist)
        .filter(func.lower(Song.title) == normalized_title)
        .first()
    )


def was_recently_played(session, song_id: int) -> bool:
    cutoff = datetime.utcnow() - timedelta(seconds=settings.ignore_window_seconds)
    last_play = (
        session.query(Play)
        .filter(Play.song_id == song_id)
        .order_by(Play.detected_at.desc())
        .first()
    )
    return bool(last_play and last_play.detected_at >= cutoff)


def record_detection(session, station: Station, detection: dict) -> None:
    song = get_existing_song(session, detection["artist"], detection["title"])
    now = datetime.utcnow()

    if song and was_recently_played(session, song.id):
        logger.debug(
            "Duplicate within %ds window — skipping: %s – %s",
            settings.ignore_window_seconds,
            detection["artist"],
            detection["title"],
        )
        return

    if song is None:
        song = Song(
            artist=detection["artist"],
            title=detection["title"],
            album=detection.get("album"),
            musicbrainz_id=detection.get("musicbrainz_id"),
            acoustid_id=detection.get("acoustid_id"),
            first_seen_at=now,
            last_seen_at=now,
        )
        session.add(song)
        session.flush()
        logger.info("New song: %s – %s", detection["artist"], detection["title"])
    else:
        song.album = detection.get("album") or song.album
        song.musicbrainz_id = detection.get("musicbrainz_id") or song.musicbrainz_id
        song.acoustid_id = detection.get("acoustid_id") or song.acoustid_id
        song.last_seen_at = now

    play = Play(
        song_id=song.id,
        station_name=station.name,
        detected_at=now,
        confidence=detection["confidence"],
        provider=detection["provider"],
        raw_result_json=detection["raw_result_json"],
    )
    session.add(play)
    session.commit()
    logger.info(
        "Play logged: %s – %s on %s (confidence=%.2f)",
        detection["artist"],
        detection["title"],
        station.name,
        detection["confidence"],
    )


def process_station(station: Station) -> dict | None:
    logger.debug("Processing station: %s", station.name)
    sample_path = capture_audio(station.stream_url, settings.sample_duration)
    if not sample_path:
        return None

    try:
        fingerprint_body = fingerprint_audio(sample_path)
        if not fingerprint_body:
            return None

        detection = query_acoustid(
            fingerprint_body["fingerprint"],
            fingerprint_body["duration"],
        )
        if not detection:
            return None

        if detection["confidence"] < settings.confidence_threshold:
            logger.debug(
                "Confidence too low (%.2f < %.2f) for station %s — skipping",
                detection["confidence"],
                settings.confidence_threshold,
                station.name,
            )
            return None

        detection_key = build_song_key(detection["artist"], detection["title"])
        if not detection_key:
            return None

        with SessionLocal() as session:
            record_detection(session, station, detection)
        return detection
    finally:
        if sample_path is not None and sample_path.exists():
            sample_path.unlink(missing_ok=True)


async def monitor_loop(stop_event: asyncio.Event) -> None:
    logger.info("Monitor loop started.")
    while not stop_event.is_set():
        try:
            with SessionLocal() as session:
                stations = (
                    session.query(Station)
                    .filter(Station.enabled == True)  # noqa: E712
                    .all()
                )
            logger.debug("Polling %d enabled station(s).", len(stations))
            for station in stations:
                if stop_event.is_set():
                    break
                await asyncio.to_thread(process_station, station)
        except Exception:
            logger.exception("Unexpected error during station polling.")

        # Wait for the poll interval, but wake up immediately if stop_event fires.
        try:
            await asyncio.wait_for(
                asyncio.shield(stop_event.wait()),
                timeout=settings.poll_interval_seconds,
            )
            # stop_event was set — exit the loop
            break
        except asyncio.TimeoutError:
            pass  # Normal path: interval elapsed, go around again

    logger.info("Monitor loop stopped.")
