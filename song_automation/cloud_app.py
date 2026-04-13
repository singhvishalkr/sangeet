"""Zero-arg ASGI factory for cloud deployment (Render, Railway, etc.).

Creates a MusicController in dry-run mode using the example config,
so the dashboard and API work without mpv or real audio hardware.

Start command:
    uvicorn song_automation.cloud_app:create_cloud_app --host 0.0.0.0 --port $PORT --factory
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from fastapi import FastAPI

from song_automation.api import create_app
from song_automation.controller import MusicController

_CONFIG_EXAMPLE = Path(__file__).resolve().parent.parent / "config" / "automation.example.yaml"
_CONFIG_RUNTIME = Path(__file__).resolve().parent.parent / "config" / "automation.yaml"


def create_cloud_app() -> FastAPI:
    if not _CONFIG_RUNTIME.exists():
        shutil.copy(_CONFIG_EXAMPLE, _CONFIG_RUNTIME)

    controller = MusicController(
        config_path=str(_CONFIG_RUNTIME),
        dry_run_override=True,
    )
    return create_app(controller)
