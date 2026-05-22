"""
Data preparation pipeline: downloads audio and generates Whisper transcripts
for podcast episodes from a CSV of RSS feeds.

Usage:
    python prepare_data.py feeds.csv /mnt/external/cache 2024
    python prepare_data.py feeds.csv /mnt/external/cache 2024 --max-audio-size 60

The CSV must have at minimum an 'rss_feed' column (URLs). A 'name' column is
used for cache filenames if present; otherwise the podcast title is fetched
from the feed itself.

Transcripts are saved as .txt files in the cache directory.
Run this before the analysis notebook to pre-populate the transcript cache —
the notebook will skip transcription for any episode with a cached .txt file.
"""

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add analysis package and backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "site" / "backend"))

from analysis.rss_utils import get_podcast_name, get_episodes_between_dates
from analysis.podchecker_client import download_audio, sanitize_filename, DEFAULT_MAX_AUDIO_SIZE_MB


def _read_feeds_csv(feeds_file: str) -> list[dict]:
    """Read RSS feed entries from a CSV file. Returns list of {name, rss_feed} dicts."""
    with open(feeds_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return []

    if "rss_feed" not in reader.fieldnames:
        raise ValueError(f"CSV must contain an 'rss_feed' column. Found: {reader.fieldnames}")

    return [{"name": row.get("name", "").strip(), "rss_feed": row["rss_feed"].strip()} for row in rows]


def prepare_feeds(
    feeds_file: str,
    year: int,
    data_dir: Path,
    max_audio_size_mb: float,
) -> None:
    feeds = _read_feeds_csv(feeds_file)
    if not feeds:
        print("No RSS feeds found in input file.")
        return

    start_date = datetime(year, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

    print(f"Found {len(feeds)} RSS feed(s) in {feeds_file}")
    print(f"Fetching episodes published in {year}")
    data_dir.mkdir(parents=True, exist_ok=True)

    print("Loading Whisper model...")
    import torch
    import whisper
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = whisper.load_model("small.en", device=device)

    for feed in feeds:
        rss_url = feed["rss_feed"]
        try:
            podcast_name = feed["name"] or get_podcast_name(rss_url)
            safe_podcast = sanitize_filename(podcast_name, max_length=50)
            episodes = get_episodes_between_dates(rss_url, start_date, end_date)
        except Exception as e:
            print(f"\n[rss error] {feed['name'] or rss_url}: {e}")
            continue
        print(f"\n{podcast_name} — {len(episodes)} episode(s) in {year}")

        for episode in episodes:
            safe_episode = sanitize_filename(episode.title, max_length=100)
            base = f"{safe_podcast}_{safe_episode}"
            audio_path = data_dir / f"{base}.mp3"
            transcript_path = data_dir / f"{base}.txt"

            if transcript_path.exists():
                print(f"  [skip] {episode.title}")
                continue

            if not episode.audio_url:
                print(f"  [no audio] {episode.title}")
                continue

            if not audio_path.exists():
                print(f"  Downloading: {episode.title}")
                try:
                    _, truncated = download_audio(
                        episode.audio_url, str(audio_path), max_size_mb=max_audio_size_mb
                    )
                except Exception as e:
                    print(f"  [download error] {episode.title}: {e}")
                    continue
                if truncated:
                    print(f"    Truncated at {max_audio_size_mb}MB — skipping (container format requires full file)")
                    audio_path.unlink(missing_ok=True)
                    continue
            else:
                print(f"  [cached audio] {episode.title}")

            print(f"  Transcribing...")
            try:
                transcript = model.transcribe(str(audio_path))["text"]
            except Exception as e:
                print(f"  [transcribe error] {episode.title}: {e}")
                audio_path.unlink(missing_ok=True)
                continue
            transcript_path.write_text(transcript, encoding="utf-8")
            print(f"  Saved: {transcript_path.name}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download and transcribe podcast episodes from a CSV of RSS feeds."
    )
    parser.add_argument("feeds_file", help="Path to CSV file with RSS feeds (must have 'rss_feed' column)")
    parser.add_argument("data_dir", type=Path, help="Directory for cached audio and transcripts")
    parser.add_argument("year", type=int, help="Year to fetch episodes for (e.g. 2024)")
    parser.add_argument(
        "--max-audio-size",
        type=float,
        default=DEFAULT_MAX_AUDIO_SIZE_MB,
        metavar="MB",
        help=f"Maximum audio download size in MB (default: {DEFAULT_MAX_AUDIO_SIZE_MB})",
    )
    args = parser.parse_args()

    prepare_feeds(
        feeds_file=args.feeds_file,
        year=args.year,
        data_dir=args.data_dir,
        max_audio_size_mb=args.max_audio_size,
    )


if __name__ == "__main__":
    main()
