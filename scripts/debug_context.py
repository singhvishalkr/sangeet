"""Quick debug script to check what the controller would decide right now."""
import logging
import sys

sys.stdout.reconfigure(line_buffering=True)
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

from datetime import datetime
from zoneinfo import ZoneInfo

from song_automation.controller import MusicController

c = MusicController(config_path="config/automation.yaml", dry_run_override=True)
print("Config loaded OK")
print(f"Playlists: {len(c.config.playlists)}")
print(f"Schedule slots: {len(c.config.schedule)}")
print(f"Player exe: {c.config.player.executable}")

now = datetime.now(ZoneInfo("Asia/Calcutta"))
print(f"\nCurrent time: {now}")
print(f"Day: {now.strftime('%A')}")

ctx = c._context.build(now)
print(f"\nHolidays: {ctx.holiday_names}")
print(f"Weather: {ctx.weather}")
print(f"Time period: {ctx.time_period}")
print(f"Season: {ctx.season}")

recent = c._storage.recent_playlist_ids(c.config.smart_rotation.recent_session_window)
print(f"Recent playlists: {recent}")

from datetime import timezone as tz
override = c._storage.get_active_override(datetime.now(tz.utc))
decision = c._resolver.resolve(ctx, override, recent)
print(f"\nDecision: action={decision.action}")
print(f"  Slot: {decision.slot.id if decision.slot else 'None'}")
print(f"  Playlist: {decision.playlist.id if decision.playlist else 'None'}")
print(f"  Reason: {decision.reason}")
print(f"  Reasons: {decision.reasons}")
print(f"  Target volume: {decision.target_volume}")
