"""
Generate M3U playlists from the downloaded song library.
Smart sequencing: groups songs by theme, randomizes within groups,
ensures variety across days.
"""
import random
import hashlib
from datetime import date
from pathlib import Path

MUSIC_ROOT = Path(r"C:\Users\vishal\Music\SongAutomation")
PLAYLIST_DIR = MUSIC_ROOT / "playlists"


def collect_mp3s(folder: Path) -> list[Path]:
    """Recursively collect all .mp3 files under a folder."""
    if not folder.exists():
        return []
    return sorted(folder.rglob("*.mp3"))


def write_m3u(name: str, files: list[Path], shuffle: bool = False):
    """Write an M3U playlist file."""
    PLAYLIST_DIR.mkdir(parents=True, exist_ok=True)
    out = PLAYLIST_DIR / f"{name}.m3u"
    entries = list(files)
    if shuffle:
        random.shuffle(entries)
    with open(out, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for p in entries:
            f.write(f"{p}\n")
    print(f"  [{len(entries):3d} tracks] {out.name}")
    return out


def day_seeded_shuffle(files: list[Path], seed_extra: str = "") -> list[Path]:
    """Shuffle deterministically based on today's date so each day is different."""
    seed = hashlib.md5(f"{date.today().isoformat()}{seed_extra}".encode()).hexdigest()
    rng = random.Random(seed)
    result = list(files)
    rng.shuffle(result)
    return result


def main():
    print("Generating playlists...")
    print(f"Music root: {MUSIC_ROOT}")
    print()

    # ── Morning Bhajans ──
    morning = collect_mp3s(MUSIC_ROOT / "morning_bhajans")
    write_m3u("morning-bhajans", morning, shuffle=True)

    # Split morning bhajans by keyword for themed playlists
    shiv_keywords = ["shiv", "omkara", "shankar", "bhole", "namah shivaya"]
    devi_keywords = ["lakshmi", "ambe", "gauri", "mahalakshmi", "devi", "durga"]
    krishna_keywords = ["krishna", "govind", "gopal", "kunj bihari", "madhurashtakam", "radhe", "shyam", "achyutam"]
    hanuman_keywords = ["hanuman", "chalisa", "sankat", "pavansut"]
    ram_keywords = ["ram", "sita", "raghupati", "payoji"]

    def filter_by_keywords(files: list[Path], keywords: list[str]) -> list[Path]:
        result = []
        for f in files:
            name_lower = f.stem.lower()
            if any(kw in name_lower for kw in keywords):
                result.append(f)
        return result

    shiv_songs = filter_by_keywords(morning, shiv_keywords)
    devi_songs = filter_by_keywords(morning, devi_keywords)
    krishna_songs = filter_by_keywords(morning, krishna_keywords)
    hanuman_songs = filter_by_keywords(morning, hanuman_keywords)
    ram_songs = filter_by_keywords(morning, ram_keywords)

    if shiv_songs:
        write_m3u("morning-shiv", shiv_songs, shuffle=True)
    if devi_songs:
        write_m3u("morning-devi", devi_songs, shuffle=True)
    if krishna_songs:
        write_m3u("morning-krishna", krishna_songs, shuffle=True)
    if hanuman_songs:
        write_m3u("morning-hanuman", hanuman_songs, shuffle=True)
    if ram_songs:
        write_m3u("morning-ram", ram_songs, shuffle=True)

    # ── Evening Aarti ──
    evening = collect_mp3s(MUSIC_ROOT / "evening_aarti")
    write_m3u("evening-aarti", evening, shuffle=True)

    # ── Night Chill (all sub-genres combined + individual) ──
    night_all = collect_mp3s(MUSIC_ROOT / "night_chill")
    write_m3u("night-chill-all", night_all, shuffle=True)

    for sub in ["hindi", "sufi", "punjabi", "instrumental", "haryanvi", "bhojpuri", "classics", "indie"]:
        sub_songs = collect_mp3s(MUSIC_ROOT / "night_chill" / sub)
        if sub_songs:
            write_m3u(f"night-{sub}", sub_songs, shuffle=True)

    # ── Weekend (all combined + individual) ──
    weekend_all = collect_mp3s(MUSIC_ROOT / "weekend")
    write_m3u("weekend-all", weekend_all, shuffle=True)

    for sub in ["hindi", "punjabi", "haryanvi", "bhojpuri"]:
        sub_songs = collect_mp3s(MUSIC_ROOT / "weekend" / sub)
        if sub_songs:
            write_m3u(f"weekend-{sub}", sub_songs, shuffle=True)

    # ── Sunday relaxed: morning bhajans + night chill classics + instrumental ──
    sunday_relaxed = (
        collect_mp3s(MUSIC_ROOT / "night_chill" / "classics")
        + collect_mp3s(MUSIC_ROOT / "night_chill" / "instrumental")
        + collect_mp3s(MUSIC_ROOT / "night_chill" / "indie")
    )
    if sunday_relaxed:
        write_m3u("sunday-relaxed", sunday_relaxed, shuffle=True)

    print("\nDone! All playlists written to:", PLAYLIST_DIR)


if __name__ == "__main__":
    main()
