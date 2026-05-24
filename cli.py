import argparse
from pathlib import Path

import uvicorn

from app.config import settings
from app.db import SessionLocal, Station, init_db
from app.monitor import process_station


def init_db_command(args):
    init_db()
    print("Database initialized.")


def add_station_command(args):
    with SessionLocal() as session:
        station = Station(
            name=args.name,
            stream_url=args.stream_url,
            enabled=not args.disabled,
        )
        session.add(station)
        session.commit()
        print(f"Added station: {station.id} - {station.name}")


def list_stations_command(args):
    with SessionLocal() as session:
        stations = session.query(Station).order_by(Station.id).all()
    if not stations:
        print("No stations configured.")
        return

    print(f"{'ID':<4} {'Enabled':<8} {'Name':<30} Stream URL")
    print("-" * 90)
    for station in stations:
        enabled = "yes" if station.enabled else "no"
        print(f"{station.id:<4} {enabled:<8} {station.name:<30} {station.stream_url}")


def set_station_enabled_command(args, enabled: bool):
    with SessionLocal() as session:
        station = session.get(Station, args.station_id)
        if station is None:
            print(f"Station {args.station_id} not found.")
            return
        station.enabled = enabled
        session.commit()
        state = "enabled" if enabled else "disabled"
        print(f"Station {station.id} ({station.name}) {state}.")


def run_once_command(args):
    with SessionLocal() as session:
        query = session.query(Station)
        if args.station_id is not None:
            query = query.filter(Station.id == args.station_id)
        else:
            query = query.filter(Station.enabled == True)
        stations = query.order_by(Station.id).all()

    if not stations:
        print("No stations found to process.")
        return

    for station in stations:
        print(f"Processing station {station.id}: {station.name}")
        detection = process_station(station)
        if detection is None:
            print("  No confident detection or a duplicate within the ignore window.")
        else:
            print(
                f"  Detected: {detection['artist']} - {detection['title']} "
                f"(confidence={detection['confidence']:.2f})"
            )


def run_server_command(args):
    print(f"Starting server on {args.host}:{args.port}")
    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=args.reload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Broadcast Music Logger CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Create the SQLite database and tables")

    add_parser = subparsers.add_parser("add-station", help="Add a new radio station")
    add_parser.add_argument("name", help="Station name")
    add_parser.add_argument("stream_url", help="Stream URL")
    add_parser.add_argument(
        "--disabled", action="store_true", help="Create the station in disabled state"
    )

    subparsers.add_parser("list-stations", help="List configured stations")

    enable_parser = subparsers.add_parser("enable-station", help="Enable a station")
    enable_parser.add_argument("station_id", type=int, help="Station ID")

    disable_parser = subparsers.add_parser("disable-station", help="Disable a station")
    disable_parser.add_argument("station_id", type=int, help="Station ID")

    run_once_parser = subparsers.add_parser("run-once", help="Process enabled stations one time")
    run_once_parser.add_argument(
        "--station-id",
        type=int,
        help="Only process a single station by ID",
    )

    server_parser = subparsers.add_parser("runserver", help="Start the FastAPI web server")
    server_parser.add_argument("--host", default="0.0.0.0", help="Host to bind")
    server_parser.add_argument("--port", type=int, default=8000, help="Port to bind")
    server_parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )

    args = parser.parse_args()

    if args.command == "init-db":
        init_db_command(args)
    elif args.command == "add-station":
        add_station_command(args)
    elif args.command == "list-stations":
        list_stations_command(args)
    elif args.command == "enable-station":
        set_station_enabled_command(args, True)
    elif args.command == "disable-station":
        set_station_enabled_command(args, False)
    elif args.command == "run-once":
        run_once_command(args)
    elif args.command == "runserver":
        run_server_command(args)


if __name__ == "__main__":
    main()
