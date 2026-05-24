# 📻 Broadcast Music Logger

A self-hosted radio airplay tracker. Point it at any internet radio stream and it will automatically identify every song that plays, count how many times each track airs, and display the results on a live web dashboard — no subscription, no third-party service, no cloud dependency.

**Stack:** Python · FastAPI · SQLite · FFmpeg · Chromaprint · AcoustID · MusicBrainz

---

## How it works

```
Radio stream URL
      │
      ▼
  FFmpeg captures a 15–20 second audio clip
      │
      ▼
  fpcalc (Chromaprint) generates an audio fingerprint
      │
      ▼
  AcoustID API identifies the track (free, open)
      │
      ├─ No confident match? → discard (speech, ads, jingles)
      │
      ▼
  MusicBrainz metadata enrichment (artist / title / album)
      │
      ├─ Same song logged in the last 5 minutes? → skip duplicate
      │
      ▼
  SQLite — song record created or updated, play logged
      │
      ▼
  FastAPI dashboard at http://localhost:8000
```

The loop repeats every 25 seconds (configurable).

---

## Features

- 🎵 Identifies songs from any internet radio stream
- 🔁 Polls continuously — configurable interval (default 25 s)
- 🧠 Ignores speech, ads, jingles, and silence when no confident match is returned
- ⏱️ Deduplicates: the same song is only logged once within a 5-minute window
- 📊 Live dashboard — most-played songs, today/week totals, full detection history
- 🗄️ SQLite — zero-config database, single file, easy to back up
- ⚙️ All settings in a single `.env` file
- 🖥️ Runs as a systemd service on any Debian/Ubuntu VPS or home server

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | |
| FFmpeg | any recent | `sudo apt install ffmpeg` |
| Chromaprint (`fpcalc`) | ≥ 1.5 | `sudo apt install chromaprint-tools` |
| AcoustID API key | — | Free — see [Getting an API key](#getting-an-acoustid-api-key) |
| Internet access | — | For the radio stream and AcoustID/MusicBrainz lookups |

---

## Getting an AcoustID API key

1. Go to **[acoustid.org/login](https://acoustid.org/login)** and create a free account.
2. Navigate to **My Applications → Register a new application**.
3. Give it any name (e.g. `broadcast-music-logger`) — the API is free for non-commercial use.
4. Copy the API key into your `.env` file as `ACOUSTID_API_KEY=...`.

---

## Installation (Debian / Ubuntu)

### 1 — System dependencies

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip ffmpeg chromaprint-tools sqlite3
```

### 2 — Clone and set up Python environment

```bash
git clone https://github.com/your-username/broadcast-music-logger.git
cd broadcast-music-logger

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

### 3 — Configure

```bash
cp .env.example .env
nano .env          # set ACOUSTID_API_KEY at minimum
```

See the [Configuration reference](#configuration-reference) for all options.

### 4 — Initialise the database

```bash
python cli.py init-db
```

### 5 — Add a radio station

```bash
python cli.py add-station "Triple J" "https://live-radio01.mediahubaustralia.com/2TJW/mp3/"
```

You can add as many stations as you like. All enabled stations are polled on every cycle.

### 6 — Start the server

```bash
python cli.py runserver
```

Open **http://localhost:8000** in your browser.

---

## Configuration reference

Copy `.env.example` to `.env` and edit as needed. Every setting has a sensible default except `ACOUSTID_API_KEY`, which is required.

| Variable | Default | Description |
|---|---|---|
| `ACOUSTID_API_KEY` | *(required)* | Your AcoustID application API key |
| `DATABASE_URL` | `sqlite:///./broadcast_music_log.db` | SQLAlchemy database URL |
| `SAMPLE_DURATION` | `18` | Audio clip length in seconds (15–20 recommended) |
| `POLL_INTERVAL_SECONDS` | `25` | Seconds between polling cycles |
| `CONFIDENCE_THRESHOLD` | `0.75` | Minimum AcoustID score to accept a match (0–1) |
| `IGNORE_WINDOW_SECONDS` | `300` | Duplicate suppression window in seconds (5 minutes) |
| `FFMPEG_PATH` | `ffmpeg` | Full path to FFmpeg binary if not on `$PATH` |
| `FPCALC_PATH` | `fpcalc` | Full path to fpcalc binary if not on `$PATH` |
| `TEMP_DIR` | `./tmp` | Directory for temporary audio sample files |

**Example `.env`:**

```dotenv
ACOUSTID_API_KEY=abc123yourkeyhere
DATABASE_URL=sqlite:///./broadcast_music_log.db
SAMPLE_DURATION=18
POLL_INTERVAL_SECONDS=25
CONFIDENCE_THRESHOLD=0.75
IGNORE_WINDOW_SECONDS=300
```

---

## CLI reference

All management is done through `cli.py`:

```
python cli.py <command> [options]
```

| Command | Description |
|---|---|
| `init-db` | Create the SQLite database and tables |
| `add-station <name> <url>` | Add a new radio station |
| `add-station <name> <url> --disabled` | Add a station in disabled state |
| `list-stations` | Show all configured stations |
| `enable-station <id>` | Enable a station |
| `disable-station <id>` | Disable a station (stops polling) |
| `run-once` | Run one detection cycle across all enabled stations |
| `run-once --station-id <id>` | Run one detection cycle for a specific station |
| `runserver` | Start the FastAPI web server (default: `0.0.0.0:8000`) |
| `runserver --host 127.0.0.1 --port 9000` | Bind to a custom host/port |
| `runserver --reload` | Enable auto-reload for development |

### Quick-start example

```bash
# Set up
python cli.py init-db
python cli.py add-station "Triple J"   "https://live-radio01.mediahubaustralia.com/2TJW/mp3/"
python cli.py add-station "Double J"   "https://live-radio01.mediahubaustralia.com/2DBW/mp3/"

# Verify detection is working before starting the server
python cli.py run-once

# Start
python cli.py runserver
```

---

## Dashboard

The dashboard at `http://localhost:8000` shows:

| Section | What it displays |
|---|---|
| **Latest detection** | Most recently identified song, station, time, and confidence score |
| **Plays today** | Total logged plays since midnight UTC |
| **Plays this week** | Total logged plays in the last 7 days |
| **Most played songs** | All songs ranked by total play count, with last-played time |
| **Raw detection history** | Last 100 individual play records with time, station, song, and confidence |

---

## Database schema

The SQLite database contains three tables:

**`songs`** — one row per unique track

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER | Primary key |
| `artist` | TEXT | Artist name |
| `title` | TEXT | Track title |
| `album` | TEXT | Album/release group (if available) |
| `musicbrainz_id` | TEXT | MusicBrainz recording ID |
| `acoustid_id` | TEXT | AcoustID fingerprint ID |
| `first_seen_at` | DATETIME | UTC time of first detection |
| `last_seen_at` | DATETIME | UTC time of most recent detection |

**`plays`** — one row per logged airplay event

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER | Primary key |
| `song_id` | INTEGER | FK → songs.id |
| `station_name` | TEXT | Name of the station |
| `detected_at` | DATETIME | UTC time of detection |
| `confidence` | REAL | AcoustID confidence score (0–1) |
| `provider` | TEXT | Detection provider (`acoustid`) |
| `raw_result_json` | TEXT | Full AcoustID API response (for debugging) |

**`stations`** — one row per configured stream

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER | Primary key |
| `name` | TEXT | Human-readable station name |
| `stream_url` | TEXT | HTTP/HTTPS stream URL |
| `enabled` | BOOLEAN | Whether this station is polled |

---

## Production deployment (systemd)

### 1 — Copy files to the server

```bash
sudo mkdir -p /opt/broadcast-music-logger
sudo cp -r . /opt/broadcast-music-logger/
sudo cp .env /opt/broadcast-music-logger/.env

cd /opt/broadcast-music-logger
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python cli.py init-db
```

### 2 — Add your stations

```bash
python cli.py add-station "My Station" "https://example.com/stream"
```

### 3 — Install and enable the systemd service

Edit `deploy/broadcast-music-logger.service` if you need to change the install path or user, then:

```bash
sudo cp deploy/broadcast-music-logger.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now broadcast-music-logger
```

### 4 — Check it is running

```bash
sudo systemctl status broadcast-music-logger
journalctl -u broadcast-music-logger -f
```

> **Note on the timer file:** `deploy/broadcast-music-logger.timer` is included for reference only. The service already has a built-in async polling loop — do **not** enable the timer alongside the service, as it would restart the whole process every 30 seconds and cause duplicate detections.

### Putting it behind Nginx (optional)

```nginx
server {
    listen 80;
    server_name radio.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Viewing logs

When running under systemd:

```bash
journalctl -u broadcast-music-logger -f
```

When running directly, logs go to stdout:

```
2024-01-15 03:42:10  INFO      app.main     Broadcast Music Logger started.
2024-01-15 03:42:10  INFO      app.monitor  Monitor loop started.
2024-01-15 03:42:28  INFO      app.monitor  Play logged: Tame Impala – Elephant on Triple J (confidence=0.93)
2024-01-15 03:42:53  DEBUG     app.monitor  Duplicate within 300s window — skipping: Tame Impala – Elephant
```

Log verbosity is controlled by the level set in `app/main.py`. The `app.*` namespace defaults to `DEBUG`; the root logger defaults to `INFO`.

---

## Troubleshooting

**The app won't start / `ImportError: cannot import name 'BaseSettings'`**  
Run `pip install -r requirements.txt` — `pydantic-settings` must be installed.

**`ffmpeg: command not found`**  
Install FFmpeg (`sudo apt install ffmpeg`) or set `FFMPEG_PATH` in `.env` to the full binary path.

**`fpcalc: command not found`**  
Install Chromaprint (`sudo apt install chromaprint-tools`) or set `FPCALC_PATH` in `.env`.

**All detections show low confidence / nothing is being logged**  
Lower `CONFIDENCE_THRESHOLD` in `.env` (try `0.5`) and run `python cli.py run-once` to test a single cycle. Check that the stream URL is accessible: `ffmpeg -i <stream_url> -t 5 test.wav`.

**The dashboard is empty but `run-once` shows detections**  
The server's monitor loop starts automatically on `runserver`. Make sure you're not running `run-once` instead.

**Duplicate plays appearing**  
Check `IGNORE_WINDOW_SECONDS` — it defaults to 300 (5 minutes). If the same song is logged more frequently than that, verify the system clock is set to UTC.

---

## Project structure

```
broadcast-music-logger/
├── app/
│   ├── __init__.py
│   ├── config.py          # Pydantic Settings — reads .env
│   ├── db.py              # SQLAlchemy ORM models
│   ├── detector.py        # FFmpeg → fpcalc → AcoustID pipeline
│   ├── monitor.py         # Async polling loop + play recording
│   ├── main.py            # FastAPI app + dashboard routes
│   └── templates/
│       └── dashboard.html # Jinja2 dashboard
├── deploy/
│   ├── broadcast-music-logger.service   # systemd service
│   └── broadcast-music-logger.timer     # systemd timer (reference only)
├── cli.py                 # Management CLI
├── requirements.txt
├── .env.example
└── README.md
```

---

## License

MIT — see [LICENSE](LICENSE) for details.
