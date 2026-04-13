"""
Song Library Downloader
Downloads curated playlists via yt-dlp (YouTube search -> best audio).
Skips already-downloaded files so it's safe to re-run.
"""
import subprocess
import sys
import os
import json
import time
import random
from pathlib import Path

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

MUSIC_ROOT = Path(r"C:\Users\vishal\Music\SongAutomation")

# ── yt-dlp common args ──────────────────────────────────────────────
YT_DLP = "yt-dlp"
COMMON_ARGS = [
    "--extract-audio",
    "--audio-format", "mp3",
    "--audio-quality", "0",          # best VBR
    "--embed-thumbnail",
    "--add-metadata",
    "--no-playlist",
    "--match-filter", "duration < 900",  # skip >15 min compilations
    "--socket-timeout", "30",
    "--retries", "3",
    "--no-overwrites",
]


def download_song(search_query: str, output_dir: Path, filename: str) -> bool:
    """Download a single song via YouTube search. Returns True on success."""
    out_path = output_dir / f"{filename}.mp3"
    if out_path.exists():
        print(f"  [SKIP] Already exists: {filename}")
        return True

    cmd = [
        YT_DLP,
        *COMMON_ARGS,
        "-o", str(output_dir / f"{filename}.%(ext)s"),
        f"ytsearch1:{search_query}",
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, timeout=120,
            encoding="utf-8", errors="replace",
        )
        if result.returncode == 0:
            print(f"  [OK]   {filename}")
            return True
        else:
            err = result.stderr[:200] if result.stderr else "unknown error"
            print(f"  [FAIL] {filename}: {err}")
            return False
    except subprocess.TimeoutExpired:
        print(f"  [TIMEOUT] {filename}")
        return False
    except Exception as e:
        print(f"  [ERROR] {filename}: {e}")
        return False


def sanitize(name: str) -> str:
    """Make filename safe."""
    for ch in r'<>:"/\|?*':
        name = name.replace(ch, "")
    return name.strip()[:80]


# ═══════════════════════════════════════════════════════════════════
# MORNING BHAJANS (Mon-Fri 7:30 AM, ~30 min)
# ═══════════════════════════════════════════════════════════════════
MORNING_BHAJANS = [
    # Ganesha
    ("Ganesh Gayatri - Anuradha Paudwal", "Anuradha Paudwal Ganesh Gayatri official T-Series Bhakti"),
    ("Jai Ganesh Jai Ganesh Deva - Anuradha Paudwal", "Anuradha Paudwal Jai Ganesh Jai Ganesh Deva aarti official"),
    ("Shendur Lal Chadhayo - Hari Om Sharan", "Hari Om Sharan Shendur Lal Chadhayo official"),
    ("Sukhkarta Dukhharta - Lata Mangeshkar", "Lata Mangeshkar Sukhkarta Dukhharta Aarti official"),
    ("Vakratunda Mahakaya - Shankar Mahadevan", "Shankar Mahadevan Vakratunda Mahakaya Ganesha official"),
    ("Om Jai Ganesh Deva - Anup Jalota", "Anup Jalota Om Jai Ganesh Deva Aarti official"),
    # Gayatri
    ("Gayatri Mantra - Anuradha Paudwal", "Anuradha Paudwal Gayatri Mantra official T-Series Bhakti"),
    ("Gayatri Mantra - Suresh Wadkar", "Suresh Wadkar Gayatri Mantra official"),
    ("Gayatri Mantra - Shankar Mahadevan", "Shankar Mahadevan Gayatri Mantra official"),
    # Vishnu
    ("Om Jai Jagdish Hare - Lata Mangeshkar", "Lata Mangeshkar Om Jai Jagdish Hare Aarti official"),
    ("Achyutam Keshavam - Anuradha Paudwal", "Anuradha Paudwal Achyutam Keshavam official"),
    ("Achyutam Keshavam - Shankar Mahadevan", "Shankar Mahadevan Achyutam Keshavam official"),
    ("Hey Govind Hey Gopal - Jagjit Singh", "Jagjit Singh Hey Govind Hey Gopal bhajan official"),
    # Krishna
    ("Aarti Kunj Bihari Ki - Hari Om Sharan", "Hari Om Sharan Aarti Kunj Bihari Ki official"),
    ("Govind Jai Jai Gopal Jai Jai - Hari Om Sharan", "Hari Om Sharan Govind Jai Jai Gopal Jai Jai official"),
    ("Shree Krishna Govind Hare Murari - Anup Jalota", "Anup Jalota Shree Krishna Govind Hare Murari official"),
    ("Madhurashtakam Adharam Madhuram - Anuradha Paudwal", "Anuradha Paudwal Madhurashtakam Adharam Madhuram official"),
    ("Radhe Krishna - Suresh Wadkar", "Suresh Wadkar Radhe Krishna bhajan official"),
    ("Shyam Teri Bansi - Jagjit Singh", "Jagjit Singh Shyam Teri Bansi official"),
    # Ram
    ("Shri Ramchandra Kripalu Bhajman - Jagjit Singh", "Jagjit Singh Shri Ramchandra Kripalu Bhajman official"),
    ("Shri Ramchandra Kripalu Bhajman - Lata Mangeshkar", "Lata Mangeshkar Shri Ramchandra Kripalu Bhajman official"),
    ("Payoji Maine Ram Ratan Dhan Payo - Lata Mangeshkar", "Lata Mangeshkar Payoji Maine Ram Ratan Dhan Payo official"),
    ("Ram Aarti - Anup Jalota", "Anup Jalota Ram Aarti Shri Ram official"),
    ("Raghupati Raghav Raja Ram - Hari Om Sharan", "Hari Om Sharan Raghupati Raghav Raja Ram official"),
    ("Sita Ram Sita Ram Kahiye - Suresh Wadkar", "Suresh Wadkar Sita Ram Sita Ram kahiye official"),
    # Shiv
    ("Shiv Aarti Om Jai Shiv Omkara - Anup Jalota", "Anup Jalota Shiv Aarti Om Jai Shiv Omkara official"),
    ("Namah Shivaya Dhun - Anuradha Paudwal", "Anuradha Paudwal Namah Shivaya dhun official"),
    ("Shiv Shankar Ko Jisne Pooja - Suresh Wadkar", "Suresh Wadkar Shiv Shankar Ko Jisne Pooja official"),
    ("Bhole Shankar - Hari Om Sharan", "Hari Om Sharan Bhole Shankar bhajan official"),
    # Hanuman
    ("Hanuman Chalisa - Hari Om Sharan", "Hari Om Sharan Hanuman Chalisa official full"),
    ("Hanuman Chalisa - Gulshan Kumar", "Gulshan Kumar Hanuman Chalisa T-Series Bhakti Sagar official"),
    ("Hanuman Ashtak - Anup Jalota", "Anup Jalota Hanuman Ashtak official"),
    ("Sankat Mochan Hanuman - Hari Om Sharan", "Hari Om Sharan Sankat Mochan Hanuman official"),
    # Lakshmi / Devi
    ("Om Jai Lakshmi Mata - Anuradha Paudwal", "Anuradha Paudwal Om Jai Lakshmi Mata Aarti official"),
    ("Mahalakshmi Ashtakam - Anuradha Paudwal", "Anuradha Paudwal Mahalakshmi Ashtakam official"),
    ("Jai Ambe Gauri - Anuradha Paudwal", "Anuradha Paudwal Jai Ambe Gauri Aarti official"),
]

# ═══════════════════════════════════════════════════════════════════
# EVENING AARTI (Mon-Fri 7:00 PM, ~30 min)
# ═══════════════════════════════════════════════════════════════════
EVENING_AARTI = [
    ("Om Jai Jagdish Hare - Lata Mangeshkar", "Om Jai Jagdish Hare Lata Mangeshkar official"),
    ("Aarti Kunj Bihari Ki - Anuradha Paudwal", "Aarti Kunj Bihari Ki Anuradha Paudwal T-Series Bhakti Sagar official"),
    ("Aarti Shri Ramayan Ji Ki - Hari Om Sharan", "Ramayan Ji Ki Aarti Hari Om Sharan official"),
    ("Om Jai Shiv Omkara - Anuradha Paudwal", "Om Jai Shiv Omkara Shiv Aarti Anuradha Paudwal T-Series Bhakti Sagar official"),
    ("Jai Ganesh Deva - Anuradha Paudwal", "Jai Ganesh Deva Ganesh Aarti Anuradha Paudwal T-Series Bhakti Sagar"),
    ("Sukhkarta Dukhharta - Lata Mangeshkar", "Sukhkarta Dukhharta Aarti Lata Mangeshkar official"),
    ("Shendur Lal Chadhayo - Anup Jalota", "Shendur Lal Chadhayo Ganesh Aarti Anup Jalota official"),
    ("Hanuman Aarti - Hari Om Sharan", "Hanuman Aarti Aarti Keejai Hanuman Lala Ki Hari Om Sharan official"),
    ("Jai Ambe Gauri - Anuradha Paudwal", "Jai Ambe Gauri Durga Aarti Anuradha Paudwal T-Series Bhakti Sagar official"),
    ("Ambe Tu Hai Jagdambe Kali - Anuradha Paudwal", "Ambe Tu Hai Jagdambe Kali Aarti Anuradha Paudwal official"),
    ("Jai Lakshmi Mata - Anuradha Paudwal", "Jai Lakshmi Mata Aarti Anuradha Paudwal T-Series Bhakti Sagar official"),
    ("Sandhya Aarti - Anuradha Paudwal", "Sandhya Aarti Anuradha Paudwal T-Series Bhakti Sagar official"),
    ("Achyutam Keshavam - Anuradha Paudwal", "Achyutam Keshavam Krishna Damodaram Anuradha Paudwal T-Series Bhakti Sagar official"),
    ("Govind Bolo Hari Gopal Bolo - Hari Om Sharan", "Govind Bolo Hari Gopal Bolo Hari Om Sharan official"),
    ("Shree Krishna Govind Hare Murari - Suresh Wadkar", "Shree Krishna Govind Hare Murari Suresh Wadkar official"),
    ("Raghupati Raghav Raja Ram - Mahendra Kapoor", "Raghupati Raghav Raja Ram Mahendra Kapoor official"),
    ("Hanuman Chalisa - Hari Om Sharan", "Hanuman Chalisa Hari Om Sharan official"),
    ("Mangal Bhavan Amangal Hari - Mahendra Kapoor", "Mangal Bhavan Amangal Hari Mahendra Kapoor Ramayan official"),
    ("Vaishnav Jan To - Lata Mangeshkar", "Vaishnav Jan To Tene Kahiye Lata Mangeshkar official"),
    ("Itna To Karna Swami - Anuradha Paudwal", "Itna To Karna Swami Anuradha Paudwal T-Series Bhakti Sagar official"),
    ("Om Namah Shivaya Dhun - Anuradha Paudwal", "Om Namah Shivaya dhun Anuradha Paudwal T-Series Bhakti Sagar official"),
    ("Payoji Maine Ram Ratan - Lata Mangeshkar", "Payoji Maine Ram Ratan Dhan Payo Lata Mangeshkar official"),
    ("Shri Ramchandra Kripalu - Lata Mangeshkar", "Shree Ramchandra Kripalu Bhajman Lata Mangeshkar official"),
]

# ═══════════════════════════════════════════════════════════════════
# NIGHT CHILL (9 PM, ~30-45 min)
# ═══════════════════════════════════════════════════════════════════
NIGHT_CHILL_HINDI = [
    ("Tum Hi Ho - Arijit Singh", "Tum Hi Ho Arijit Singh official audio"),
    ("Channa Mereya - Arijit Singh", "Channa Mereya Arijit Singh official audio"),
    ("Agar Tum Saath Ho - Arijit Singh", "Agar Tum Saath Ho Tamasha Arijit official"),
    ("Ae Dil Hai Mushkil - Arijit Singh", "Ae Dil Hai Mushkil title song Arijit official"),
    ("Phir Bhi Tumko Chahunga - Arijit Singh", "Phir Bhi Tumko Chahunga Half Girlfriend official"),
    ("Tu Jaane Na - Atif Aslam", "Tu Jaane Na Atif Ajab Prem Ki Ghazab Kahani official"),
    ("Tera Hone Laga Hoon - Atif Aslam", "Tera Hone Laga Hoon Atif Shreya official"),
    ("Tere Sang Yaara - Atif Aslam", "Tere Sang Yaara Atif Rustom official"),
    ("Jeene Laga Hoon - Atif Aslam", "Jeene Laga Hoon Atif Shreya Ramaiya Vastavaiya official"),
    ("Pal - KK Shreya Ghoshal", "Pal KK Shreya Ghoshal Jalebi official"),
    ("Alvida - KK", "Alvida KK Life in a Metro official"),
    ("Tum Se Hi - Mohit Chauhan", "Tum Se Hi Mohit Jab We Met official"),
    ("Pee Loon - Mohit Chauhan", "Pee Loon Mohit Once Upon A Time Mumbai official"),
    ("Kabira Encore - Arijit Singh", "Kabira encore Yeh Jawaani Hai Deewani official"),
    ("Teri Meri - Rahat Fateh Ali Khan", "Teri Meri Bodyguard Rahat Shreya official"),
]

NIGHT_CHILL_SUFI = [
    ("Afreen Afreen - Rahat Coke Studio", "Afreen Afreen Coke Studio Rahat Momina official"),
    ("O Re Piya - Rahat Fateh Ali Khan", "O Re Piya Rahat Aaja Nachle official"),
    ("Tumhe Dillagi - Rahat Fateh Ali Khan", "Tumhe Dillagi Bhool Jani Rahat official"),
    ("Mere Rashke Qamar - Rahat", "Mere Rashke Qamar original Rahat Baadshaho"),
    ("Yeh Jo Halka Halka Suroor - Nusrat", "Yeh Jo Halka Halka Suroor Nusrat Fateh Ali Khan"),
    ("Saiyyan - Kailash Kher", "Saiyyan Kailash Kher official"),
    ("Teri Deewani - Kailash Kher", "Teri Deewani Kailash Kher official"),
    ("Allah Ke Bande - Kailash Kher", "Allah Ke Bande Kailash Kher Waisa Bhi Hota Hai"),
]

NIGHT_CHILL_PUNJABI = [
    ("Ik Mulakaat - Satinder Sartaaj", "Ik Mulakaat Satinder Sartaaj official"),
    ("Sajjan Raazi - Satinder Sartaaj", "Sajjan Raazi Satinder Sartaaj official"),
    ("Dil Dariya - Satinder Sartaaj", "Dil Dariya Satinder Sartaaj Seasons of Sartaaj"),
    ("Cheere Waleya - Satinder Sartaaj", "Cheere Waleya Satinder Sartaaj official"),
    ("Dheeraj - Amrinder Gill", "Dheeraj Amrinder Gill Judaa 2 official"),
    ("Yaarian - Amrinder Gill", "Yaarian Amrinder Gill Judaa official"),
    ("Chan Da Tukda - Amrinder Gill", "Chan Da Tukda Amrinder Gill Angrej"),
    ("Heer - Harbhajan Mann", "Heer Harbhajan Mann official"),
]

NIGHT_CHILL_INSTRUMENTAL = [
    ("Tum Hi Ho Piano Instrumental", "Tum Hi Ho piano instrumental calm"),
    ("Lag Ja Gale Flute Instrumental", "Lag Ja Gale instrumental flute soft"),
    ("Afreen Afreen Sitar Instrumental", "Afreen Afreen instrumental sitar soft"),
    ("Pehla Nasha Guitar Instrumental", "Pehla Nasha acoustic guitar instrumental"),
    ("Kabira MTV Unplugged", "Kabira MTV Unplugged Arijit"),
]

NIGHT_CHILL_HARYANVI = [
    ("Dil Todne Se Pehle - Gulzaar Chhaniwala", "Dil Todne Se Pehle Gulzaar Chhaniwala official audio"),
    ("Bholenath - Hansraj Raghuwanshi", "Bholenath Hansraj Raghuwanshi official audio"),
]

NIGHT_CHILL_BHOJPURI = [
    ("Nimiya Ke Dariya Maiya - Manoj Tiwari", "Nimiya Ke Dariya Maiya Manoj Tiwari Bhojpuri"),
    ("Sharda Sinha Lokgeet", "Sharda Sinha Bhojpuri lokgeet slow melodious"),
    ("Chhath Puja Geet - Sharda Sinha", "Chhath Puja geet melodious Sharda Sinha"),
]

NIGHT_CHILL_CLASSICS = [
    ("Lag Ja Gale - Lata Mangeshkar", "Lag Ja Gale Lata Woh Kaun Thi official"),
    ("Ajeeb Dastan Hai Yeh - Lata", "Ajeeb Dastan Hai Yeh Lata official"),
    ("Tere Bina Zindagi Se - Kishore Lata", "Tere Bina Zindagi Se Kishore Lata Aandhi"),
    ("O Saathi Re - Kishore Kumar", "O Saathi Re Kishore Muqaddar Ka Sikandar"),
    ("Pal Pal Dil Ke Paas - Kishore Kumar", "Pal Pal Dil Ke Paas Kishore Blackmail"),
    ("Chaudhvin Ka Chand - Rafi", "Chaudhvin Ka Chand Ho Rafi official"),
    ("Abhi Na Jao Chhod Kar - Rafi Asha", "Abhi Na Jao Chhod Kar Rafi Asha Hum Dono"),
]

NIGHT_CHILL_INDIE = [
    ("Baarishein - Anuv Jain", "Baarishein Anuv Jain official audio"),
    ("Gul - Anuv Jain", "Gul Anuv Jain official audio"),
    ("cold mess - Prateek Kuhad", "cold mess Prateek Kuhad official"),
    ("Kasoor - Prateek Kuhad", "Kasoor Prateek Kuhad official"),
]

# ═══════════════════════════════════════════════════════════════════
# WEEKEND JAMS (Sat-Sun, all day)
# ═══════════════════════════════════════════════════════════════════
WEEKEND_HINDI = [
    ("Abhi Toh Party Shuru Hui Hai - Badshah", "Abhi Toh Party Shuru Hui Hai Badshah official video"),
    ("Kar Gayi Chull - Badshah", "Kar Gayi Chull Kapoor and Sons Badshah official"),
    ("DJ Waley Babu - Badshah", "DJ Waley Babu Badshah official video"),
    ("Genda Phool - Badshah", "Genda Phool Badshah Payal Dev official"),
    ("Kala Chashma - Badshah", "Kala Chashma Baar Baar Dekho official"),
    ("Naach Meri Rani - Guru Randhawa", "Naach Meri Rani Guru Randhawa official"),
    ("High Rated Gabru - Guru Randhawa", "High Rated Gabru Guru Randhawa official"),
    ("Suit Suit - Guru Randhawa", "Suit Suit Hindi Medium Guru Randhawa official"),
    ("Lungi Dance - Honey Singh", "Lungi Dance Chennai Express Honey Singh official"),
    ("Blue Eyes - Honey Singh", "Blue Eyes Yo Yo Honey Singh official"),
    ("Angreji Beat - Honey Singh", "Angreji Beat Cocktail Honey Singh official"),
    ("Badtameez Dil - Benny Dayal", "Badtameez Dil Yeh Jawaani Hai Deewani official"),
    ("London Thumakda", "London Thumakda Queen official video"),
    ("Gallan Goodiyan", "Gallan Goodiyan Dil Dhadakne Do official"),
    ("Nashe Si Chadh Gayi - Arijit", "Nashe Si Chadh Gayi Befikre Arijit Singh official"),
    ("Apna Time Aayega - Ranveer", "Apna Time Aayega Gully Boy official"),
    ("First Class - Arijit", "First Class Kalank Arijit Singh official"),
    ("Slow Motion - Bharat", "Slow Motion Bharat Nakash Aziz Shreya official"),
    ("Ilahi - Mohit Chauhan", "Ilahi Yeh Jawaani Hai Deewani Mohit Chauhan official"),
    ("Love You Zindagi", "Love You Zindagi Dear Zindagi official"),
    ("Udd Gaye - Ritviz", "Udd Gaye Ritviz official audio"),
]

WEEKEND_PUNJABI = [
    ("Brown Munde - AP Dhillon", "Brown Munde AP Dhillon official video"),
    ("Insane - AP Dhillon", "Insane AP Dhillon official video"),
    ("Toxic - AP Dhillon", "Toxic AP Dhillon official video"),
    ("Excuses - AP Dhillon", "Excuses AP Dhillon official video"),
    ("5 Taara - Diljit Dosanjh", "5 Taara Diljit Dosanjh official"),
    ("GOAT - Diljit Dosanjh", "GOAT Diljit Dosanjh official"),
    ("Proper Patola - Diljit Badshah", "Proper Patola Namaste England Diljit Badshah official"),
    ("Patiala Peg - Diljit Dosanjh", "Patiala Peg Diljit Dosanjh official"),
    ("So High - Sidhu Moosewala", "So High Sidhu Moose Wala official"),
    ("Same Beef - Sidhu Moosewala", "Same Beef Sidhu Moose Wala Bohemia official"),
    ("Levels - Sidhu Moosewala", "Levels Sidhu Moose Wala official"),
    ("Dont Look - Karan Aujla", "Don't Look Karan Aujla official"),
    ("Softly - Karan Aujla", "Softly Karan Aujla official"),
    ("Baller - Shubh", "Baller Shubh official video"),
    ("Still Rollin - Shubh", "Still Rollin Shubh official"),
    ("295 - Sidhu Moosewala", "295 Sidhu Moose Wala official"),
    ("Lover - Diljit Dosanjh", "Lover Diljit Dosanjh official"),
    ("Cheques - Shubh", "Cheques Shubh official"),
]

WEEKEND_HARYANVI = [
    ("Teri Aankhya Ka Yo Kajal - Sapna", "Teri Aankhya Ka Yo Kajal Sapna Choudhary official"),
    ("52 Gaj Ka Daman - Renuka Panwar", "52 Gaj Ka Daman Renuka Panwar official"),
    ("Yaar Haryane Te - Gulzaar Chhaniwala", "Yaar Haryane Te Gulzaar Chhaniwala official"),
    ("Desi Desi Na Bolya Kar - Raju Punjabi", "Desi Desi Na Bolya Kar Chori Re Raju Punjabi official"),
    ("Filter - Gulzaar Chhaniwala", "Filter Gulzaar Chhaniwala official"),
    ("Middle Class - Gulzaar Chhaniwala", "Middle Class Gulzaar Chhaniwala official"),
]

WEEKEND_BHOJPURI = [
    ("Lollypop Lagelu - Pawan Singh", "Lollypop Lagelu Pawan Singh official"),
    ("Raat Diya Buta Ke - Pawan Singh", "Raat Diya Buta Ke Pawan Singh official"),
    ("Sarso Ke Sagiya - Khesari Lal", "Sarso Ke Sagiya Khesari Lal Yadav official"),
    ("Hello Kaun - Ritesh Pandey", "Hello Kaun Ritesh Pandey official"),
]


def download_batch(songs: list[tuple[str, str]], output_dir: Path, label: str):
    """Download a batch of (title, search_query) pairs."""
    print(f"\n{'='*60}")
    print(f"  {label} -> {output_dir}")
    print(f"  {len(songs)} songs to process")
    print(f"{'='*60}")
    ok, fail = 0, 0
    for title, query in songs:
        fname = sanitize(title)
        if download_song(query, output_dir, fname):
            ok += 1
        else:
            fail += 1
        time.sleep(random.uniform(1.0, 3.0))  # polite delay
    print(f"  -- {label}: {ok} ok, {fail} failed --")
    return ok, fail


def main():
    total_ok, total_fail = 0, 0

    batches = [
        (MORNING_BHAJANS, MUSIC_ROOT / "morning_bhajans", "Morning Bhajans"),
        (EVENING_AARTI, MUSIC_ROOT / "evening_aarti", "Evening Aarti"),
        (NIGHT_CHILL_HINDI, MUSIC_ROOT / "night_chill" / "hindi", "Night Chill - Hindi"),
        (NIGHT_CHILL_SUFI, MUSIC_ROOT / "night_chill" / "sufi", "Night Chill - Sufi"),
        (NIGHT_CHILL_PUNJABI, MUSIC_ROOT / "night_chill" / "punjabi", "Night Chill - Punjabi"),
        (NIGHT_CHILL_INSTRUMENTAL, MUSIC_ROOT / "night_chill" / "instrumental", "Night Chill - Instrumental"),
        (NIGHT_CHILL_HARYANVI, MUSIC_ROOT / "night_chill" / "haryanvi", "Night Chill - Haryanvi"),
        (NIGHT_CHILL_BHOJPURI, MUSIC_ROOT / "night_chill" / "bhojpuri", "Night Chill - Bhojpuri"),
        (NIGHT_CHILL_CLASSICS, MUSIC_ROOT / "night_chill" / "classics", "Night Chill - Classics"),
        (NIGHT_CHILL_INDIE, MUSIC_ROOT / "night_chill" / "indie", "Night Chill - Indie"),
        (WEEKEND_HINDI, MUSIC_ROOT / "weekend" / "hindi", "Weekend - Hindi"),
        (WEEKEND_PUNJABI, MUSIC_ROOT / "weekend" / "punjabi", "Weekend - Punjabi"),
        (WEEKEND_HARYANVI, MUSIC_ROOT / "weekend" / "haryanvi", "Weekend - Haryanvi"),
        (WEEKEND_BHOJPURI, MUSIC_ROOT / "weekend" / "bhojpuri", "Weekend - Bhojpuri"),
    ]

    for songs, out_dir, label in batches:
        out_dir.mkdir(parents=True, exist_ok=True)
        ok, fail = download_batch(songs, out_dir, label)
        total_ok += ok
        total_fail += fail

    print(f"\n{'='*60}")
    print(f"  DOWNLOAD COMPLETE")
    print(f"  Total: {total_ok} downloaded, {total_fail} failed")
    print(f"  Library: {MUSIC_ROOT}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
