"""
Build a transcript dataset CSV from RSS feeds and a data directory.

Uses transcript files on disk as the primary source of truth, then enriches
each row with RSS metadata (date, audio URL, episode title) where available.
Episodes with known RSS dates outside the requested year are excluded; transcripts
with no RSS match (feed no longer exposes old episodes) are included with an
empty date so they are not silently dropped.

Includes rss_feed and other feed-level columns so each episode can be traced
back to its source feed.

Usage:
    python build_dataset_v2.py feeds.csv /mnt/d/dev/data/podchecker/transcripts 2025
    python build_dataset_v2.py feeds.csv /mnt/d/dev/data/podchecker/transcripts 2025 -o dataset_v2.csv
"""

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from analysis.rss_utils import get_podcast_name, parse_rss_file
from analysis.podchecker_client import sanitize_filename


def _read_feeds_csv_full(feeds_file: str) -> list[dict]:
    """Read all columns from feeds CSV."""
    with open(feeds_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return []
    if "rss_feed" not in reader.fieldnames:
        raise ValueError(f"CSV must contain an 'rss_feed' column. Found: {reader.fieldnames}")

    return [{k: v.strip() for k, v in row.items()} for row in rows]


def build_dataset(
    feeds_file: str,
    data_dir: Path,
    year: int,
) -> pd.DataFrame:
    feeds = _read_feeds_csv_full(feeds_file)
    start_date = datetime(year, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

    rows = []
    for feed in feeds:
        rss_url = feed["rss_feed"]
        feed_name = feed.get("name", "").strip()

        try:
            podcast_name = feed_name or get_podcast_name(rss_url)
        except Exception as e:
            print(f"[rss error] {feed_name or rss_url}: {e}")
            podcast_name = feed_name or rss_url

        safe_podcast = sanitize_filename(podcast_name, max_length=50)

        # Build stem -> Episode index from all available RSS history (not date-filtered).
        # Many feeds (e.g. ART19) only expose recent episodes, so this may be partial.
        rss_by_stem: dict = {}
        try:
            for ep in parse_rss_file(rss_url):
                safe_ep = sanitize_filename(ep.title, max_length=100)
                rss_by_stem[f"{safe_podcast}_{safe_ep}"] = ep
        except Exception as e:
            print(f"[rss warning] {podcast_name}: {e}")

        # Filesystem is the primary source.
        transcript_files = sorted(data_dir.glob(f"{safe_podcast}_*.txt"))

        included = 0
        skipped_year = 0
        for transcript_path in transcript_files:
            stem = transcript_path.stem
            ep = rss_by_stem.get(stem)

            if ep:
                pub = ep.pub_date.astimezone(timezone.utc)
                if not (start_date <= pub <= end_date):
                    skipped_year += 1
                    continue
                date_str = pub.strftime("%Y-%m-%d")
                episode_name = ep.title
                audio_url = ep.audio_url or ""
            else:
                # No RSS match — transcript collected but feed no longer exposes this episode.
                # Include with empty date rather than silently drop.
                date_str = ""
                episode_name = stem[len(safe_podcast) + 1:].replace("_", " ")
                audio_url = ""

            rows.append({
                "podcast_name": podcast_name,
                "rss_feed": rss_url,
                "network": feed.get("network", ""),
                "host": feed.get("host", ""),
                "spotify_rank": feed.get("spotify_rank", ""),
                "date": date_str,
                "episode_name": episode_name,
                "transcript_file": transcript_path.name,
                "audio_url": audio_url,
            })
            included += 1

        rss_in_year = sum(
            1 for ep in rss_by_stem.values()
            if start_date <= ep.pub_date.astimezone(timezone.utc) <= end_date
        )
        no_rss_match = included - (rss_in_year - skipped_year)
        print(
            f"{podcast_name} — {included} included"
            f"  [RSS in {year}: {rss_in_year},"
            f" skipped other years: {skipped_year},"
            f" no RSS match (disk-only): {no_rss_match}]"
        )

    columns = [
        "podcast_name", "rss_feed", "network", "host", "spotify_rank",
        "date", "episode_name", "transcript_file", "audio_url",
    ]
    return pd.DataFrame(rows, columns=columns)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a transcript dataset CSV from RSS feeds (filesystem-first)."
    )
    parser.add_argument("feeds_file", help="CSV with RSS feeds (must have 'name' and 'rss_feed' columns)")
    parser.add_argument("data_dir", type=Path, help="Directory containing transcript .txt files")
    parser.add_argument("year", type=int, help="Year to fetch episodes for (e.g. 2025)")
    parser.add_argument("-o", "--output", default="dataset_v2.csv", help="Output CSV path (default: dataset_v2.csv)")
    args = parser.parse_args()

    df = build_dataset(args.feeds_file, args.data_dir, args.year)
    df.to_csv(args.output, index=False)
    print(f"\nSaved {len(df)} rows to {args.output}")


if __name__ == "__main__":
    main()
