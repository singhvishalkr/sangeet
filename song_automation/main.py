from __future__ import annotations

import argparse
import time

import uvicorn

from song_automation.api import create_app
from song_automation.controller import MusicController
from song_automation.logging_config import setup_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sangeet — intelligent music automation")
    parser.add_argument("--config", required=True, help="Path to the YAML configuration file")
    parser.add_argument("--dry-run", action="store_true", help="Run without controlling mpv")
    parser.add_argument("--no-api", action="store_true", help="Run the scheduler loop without the HTTP API")
    return parser


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    controller = MusicController(config_path=args.config, dry_run_override=args.dry_run)

    if args.no_api or not controller.config.api.enabled:
        controller.start()
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            controller.stop()
        return

    app = create_app(controller)
    uvicorn.run(app, host=controller.config.api.host, port=controller.config.api.port)


if __name__ == "__main__":
    main()
