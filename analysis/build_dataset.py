"""
Build a transcript dataset CSV from RSS feeds and a data directory.

Pulls episode metadata (name, date) from each RSS feed in the feeds CSV,
computes the expected transcript filename using the same naming logic as
prepare_data.py, and writes a dataset CSV with one row per episode.

Usage:
    python build_dataset.py feeds.csv /mnt/d/dev/data/podchecker 2025
    python build_dataset.py feeds.csv /mnt/d/dev/data/podchecker 2025 -o dataset.csv
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from analysis.rss_utils import get_episodes_between_dates, get_podcast_name
from analysis.podchecker_client import sanitize_filename
from analysis.prepare_data import _read_feeds_csv


def build_dataset(
    feeds_file: str,
    data_dir: Path,
    year: int,
) -> pd.DataFrame:
    feeds = _read_feeds_csv(feeds_file)
    start_date = datetime(year, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

    rows = []
    for feed in feeds:
        rss_url = feed["rss_feed"]
        try:
            podcast_name = feed["name"] or get_podcast_name(rss_url)
            episodes = get_episodes_between_dates(rss_url, start_date, end_date)
        except Exception as e:
            print(f"[rss error] {feed['name'] or rss_url}: {e}")
            continue

        print(f"{podcast_name} — {len(episodes)} episode(s)")
        safe_podcast = sanitize_filename(podcast_name, max_length=50)

        for episode in episodes:
            safe_episode = sanitize_filename(episode.title, max_length=100)
            transcript_filename = f"{safe_podcast}_{safe_episode}.txt"
            rows.append({
                "podcast_name": podcast_name,
                "date": episode.pub_date.strftime("%Y-%m-%d"),
                "episode_name": episode.title,
                "transcript_file": transcript_filename,
                "audio_url": episode.audio_url or "",
            })

    return pd.DataFrame(rows, columns=["podcast_name", "date", "episode_name", "transcript_file", "audio_url"])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a transcript dataset CSV from RSS feeds."
    )
    parser.add_argument("feeds_file", help="CSV with RSS feeds (must have 'name' and 'rss_feed' columns)")
    parser.add_argument("data_dir", type=Path, help="Directory containing transcript .txt files")
    parser.add_argument("year", type=int, help="Year to fetch episodes for (e.g. 2025)")
    parser.add_argument("-o", "--output", default="dataset.csv", help="Output CSV path (default: dataset.csv)")
    args = parser.parse_args()

    df = build_dataset(args.feeds_file, args.data_dir, args.year)
    df.to_csv(args.output, index=False)
    print(f"\nSaved {len(df)} rows to {args.output}")


if __name__ == "__main__":
    main()
