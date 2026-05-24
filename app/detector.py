import json
import logging
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from .config import settings

logger = logging.getLogger(__name__)

FINGERPRINT_URL = "https://api.acoustid.org/v2/lookup"


def normalize_text(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[\W_]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def capture_audio(stream_url: str, duration: int) -> Optional[Path]:
    tmp_dir = Path(settings.temp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    sample_file = tmp_dir / f"sample-{datetime.utcnow().timestamp():.0f}.wav"
    ffmpeg = shutil.which(settings.ffmpeg_path) or settings.ffmpeg_path
    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        stream_url,
        "-t",
        str(duration),
        "-ac",
        "1",
        "-ar",
        "44100",
        str(sample_file),
    ]
    logger.debug("Capturing %ds audio from %s", duration, stream_url)
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        logger.debug("Audio captured to %s", sample_file)
        return sample_file
    except subprocess.CalledProcessError as exc:
        logger.warning(
            "FFmpeg failed for %s (exit %d): %s",
            stream_url,
            exc.returncode,
            exc.stderr.strip(),
        )
        if sample_file.exists():
            sample_file.unlink(missing_ok=True)
        return None


def fingerprint_audio(sample_path: Path) -> Optional[Dict[str, Any]]:
    fpcalc = shutil.which(settings.fpcalc_path) or settings.fpcalc_path
    logger.debug("Fingerprinting %s", sample_path)
    try:
        result = subprocess.run(
            [fpcalc, str(sample_path)],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        logger.warning(
            "fpcalc failed for %s (exit %d): %s",
            sample_path,
            exc.returncode,
            exc.stderr.strip(),
        )
        return None

    duration = None
    fingerprint = None

    for line in result.stdout.splitlines():
        if line.startswith("DURATION="):
            duration = int(line.split("=", 1)[1].strip())
        elif line.startswith("FINGERPRINT="):
            fingerprint = line.split("=", 1)[1].strip()

    if not fingerprint or not duration:
        logger.warning("fpcalc produced no usable output for %s", sample_path)
        return None

    logger.debug("Fingerprint generated (duration=%ds)", duration)
    return {"fingerprint": fingerprint, "duration": duration}


def query_acoustid(fingerprint: str, duration: int) -> Optional[Dict[str, Any]]:
    params = {
        "client": settings.acoustid_api_key,
        "duration": duration,
        "fingerprint": fingerprint,
        "meta": "recordings+releasegroups+recordingids",
    }
    logger.debug("Querying AcoustID (duration=%ds)", duration)
    try:
        response = requests.get(FINGERPRINT_URL, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        logger.warning("AcoustID request failed: %s", exc)
        return None
    except ValueError as exc:
        logger.warning("AcoustID returned invalid JSON: %s", exc)
        return None

    if payload.get("status") != "ok":
        logger.warning("AcoustID returned non-ok status: %s", payload.get("status"))
        return None

    results = payload.get("results", [])
    if not results:
        logger.debug("AcoustID returned no results")
        return None

    best = max(results, key=lambda item: item.get("score", 0.0))
    score = float(best.get("score", 0.0))
    recordings = best.get("recordings", [])
    if not recordings:
        logger.debug("AcoustID best result has no recordings (score=%.2f)", score)
        return None

    recording = recordings[0]
    artist = None
    if recording.get("artists"):
        artist = recording["artists"][0].get("name")
    title = recording.get("title")
    album = None
    releasegroups = recording.get("releasegroups") or []
    if releasegroups:
        album = releasegroups[0].get("title")

    if not artist or not title:
        logger.debug("AcoustID result missing artist or title (score=%.2f)", score)
        return None

    acoustid_id = best.get("id")
    musicbrainz_id = recording.get("id")

    logger.debug(
        "AcoustID match: %s – %s (score=%.2f, mbid=%s)",
        artist,
        title,
        score,
        musicbrainz_id,
    )
    return {
        "artist": artist,
        "title": title,
        "album": album,
        "musicbrainz_id": musicbrainz_id,
        "acoustid_id": acoustid_id,
        "confidence": score,
        "provider": "acoustid",
        "raw_result_json": json.dumps(payload),
    }


def build_song_key(artist: str, title: str) -> str:
    return f"{normalize_text(artist)}|{normalize_text(title)}"
