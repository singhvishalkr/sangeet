"""Backup and restore utility for Sangeet data."""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def backup(data_dir: str, output_dir: str) -> None:
    data_path = Path(data_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    db_src = data_path / "controller.db"
    if db_src.exists():
        db_dst = output_path / f"controller_{timestamp}.db"
        conn = sqlite3.connect(str(db_src))
        backup_conn = sqlite3.connect(str(db_dst))
        conn.backup(backup_conn)
        backup_conn.close()
        conn.close()
        print(f"Database backed up to {db_dst}")

    config_src = Path("config")
    if config_src.is_dir():
        for yaml_file in config_src.glob("*.yaml"):
            dst = output_path / f"{yaml_file.stem}_{timestamp}.yaml"
            shutil.copy2(yaml_file, dst)
            print(f"Config backed up to {dst}")

    print(f"Backup complete: {output_path}")


def restore(backup_db: str, data_dir: str) -> None:
    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)

    src = Path(backup_db)
    if not src.exists():
        print(f"Backup file not found: {src}")
        return

    dst = data_path / "controller.db"
    if dst.exists():
        archive = dst.with_suffix(f".pre_restore_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.db")
        shutil.move(str(dst), str(archive))
        print(f"Existing DB archived to {archive}")

    shutil.copy2(str(src), str(dst))
    print(f"Database restored from {src}")


def export_json(data_dir: str, output_file: str) -> None:
    db_path = Path(data_dir) / "controller.db"
    if not db_path.exists():
        print("No database found")
        return

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    data = {}
    for table in ["playback_sessions", "overrides", "events", "decision_traces", "feedback_events", "preference_weights"]:
        try:
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
            data[table] = [dict(r) for r in rows]
        except sqlite3.OperationalError:
            data[table] = []

    conn.close()

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"Exported {sum(len(v) for v in data.values())} records to {output_file}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sangeet backup/restore")
    sub = parser.add_subparsers(dest="command")

    bp = sub.add_parser("backup", help="Backup database and config")
    bp.add_argument("--data-dir", default="data")
    bp.add_argument("--output-dir", default="backups")

    rp = sub.add_parser("restore", help="Restore database from backup")
    rp.add_argument("backup_file", help="Path to backup .db file")
    rp.add_argument("--data-dir", default="data")

    ep = sub.add_parser("export", help="Export all data as JSON")
    ep.add_argument("--data-dir", default="data")
    ep.add_argument("--output", default="export.json")

    args = parser.parse_args()
    if args.command == "backup":
        backup(args.data_dir, args.output_dir)
    elif args.command == "restore":
        restore(args.backup_file, args.data_dir)
    elif args.command == "export":
        export_json(args.data_dir, args.output)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
