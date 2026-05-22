"""
Fill missing publication dates (and optional bonus metadata) for episodes in a
dataset CSV using the PodcastIndex API.

For episodes where the RSS feed no longer exposes the episode, this script
looks up the full episode history from PodcastIndex and matches by reconstructing
the expected transcript filename from the PodcastIndex title, which is more
reliable than fuzzy title matching.

Bonus metadata fetched per episode (added as new columns):
  - duration_s      : episode duration in seconds
  - transcript_url  : URL to publisher-provided transcript (if any)
  - pi_persons      : JSON list of hosts/guests with roles (podcasting 2.0)
  - pi_episode_num  : episode number (podcasting 2.0)
  - pi_season_num   : season number (podcasting 2.0)

Podcast-level metadata (written to a separate summary CSV):
  - pi_trend_score  : PodcastIndex trending score (relative, not raw listens)
  - pi_episode_count: total episode count indexed by PodcastIndex
  - itunes_id       : Apple Podcasts ID (useful for cross-referencing)

Note on listen counts: PodcastIndex does not expose raw download/listen
statistics — those are held by podcast hosting platforms. For popularity
signals, see Listen Notes API (listen_score, global rank).

Usage:
    export PODCASTINDEX_API_KEY=...
    export PODCASTINDEX_API_SECRET=...
    python pull_publication_dates.py episode_mappings_v2.csv -o episode_mappings_v2_dated.csv

PodcastIndex API keys: https://api.podcastindex.org/
"""

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from analysis.podchecker_client import sanitize_filename


PI_BASE = "https://api.podcastindex.org/api/1.0"
MAX_EPISODES_PER_FEED = 1000  # PodcastIndex hard cap per request


def _auth_headers(api_key: str, api_secret: str) -> dict:
    epoch = str(int(time.time()))
    auth_hash = hashlib.sha1((api_key + api_secret + epoch).encode()).hexdigest()
    return {
        "X-Auth-Key": api_key,
        "X-Auth-Date": epoch,
        "Authorization": auth_hash,
        "User-Agent": "PodChecker/1.0",
    }


def fetch_podcast_info(rss_url: str, api_key: str, api_secret: str) -> dict:
    """Fetch podcast-level metadata from PodcastIndex."""
    r = requests.get(
        f"{PI_BASE}/podcasts/byfeedurl",
        params={"url": rss_url},
        headers=_auth_headers(api_key, api_secret),
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    feed = data.get("feed", {})
    return {
        "pi_trend_score": feed.get("trendScore"),
        "pi_episode_count": feed.get("episodeCount"),
        "itunes_id": feed.get("itunesId"),
    }


def fetch_episodes(rss_url: str, api_key: str, api_secret: str) -> list[dict]:
    """Fetch all available episodes for a feed from PodcastIndex."""
    r = requests.get(
        f"{PI_BASE}/episodes/byfeedurl",
        params={"url": rss_url, "max": MAX_EPISODES_PER_FEED, "fulltext": True},
        headers=_auth_headers(api_key, api_secret),
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("items", [])


def build_episode_index(
    episodes: list[dict],
    safe_podcast: str,
) -> dict[str, dict]:
    """
    Index PodcastIndex episodes by their expected transcript filename stem.
    This matches the naming logic in prepare_data.py / podchecker_client.py.
    """
    index = {}
    for ep in episodes:
        title = ep.get("title", "")
        stem = f"{safe_podcast}_{sanitize_filename(title, max_length=100)}"
        index[stem] = ep
    return index


def fill_dates(df: pd.DataFrame, api_key: str, api_secret: str) -> pd.DataFrame:
    df = df.copy()

    # Ensure bonus columns exist
    for col in ["duration_s", "transcript_url", "pi_persons", "pi_episode_num", "pi_season_num"]:
        if col not in df.columns:
            df[col] = None
    if "date_source" not in df.columns:
        df["date_source"] = df["date"].apply(lambda d: "rss" if pd.notna(d) else None)

    podcasts_with_missing = (
        df[df["date"].isna()]["podcast_name"].unique()
    )

    podcast_summaries = []

    for podcast_name in podcasts_with_missing:
        mask = df["podcast_name"] == podcast_name
        rss_url = df.loc[mask, "rss_feed"].iloc[0]
        safe_podcast = sanitize_filename(podcast_name, max_length=50)

        missing_mask = mask & df["date"].isna()
        n_missing = missing_mask.sum()
        print(f"\n{podcast_name} — {n_missing} missing date(s), fetching from PodcastIndex...")

        try:
            pod_info = fetch_podcast_info(rss_url, api_key, api_secret)
            pod_info["podcast_name"] = podcast_name
            pod_info["rss_feed"] = rss_url
            podcast_summaries.append(pod_info)
            print(
                f"  trend_score={pod_info['pi_trend_score']},"
                f" total_episodes={pod_info['pi_episode_count']},"
                f" itunes_id={pod_info['itunes_id']}"
            )
        except Exception as e:
            print(f"  [podcast info error] {e}")

        try:
            episodes = fetch_episodes(rss_url, api_key, api_secret)
        except Exception as e:
            print(f"  [episodes error] {e}")
            continue

        ep_index = build_episode_index(episodes, safe_podcast)
        print(f"  PodcastIndex returned {len(episodes)} episode(s)")

        filled = 0
        for idx in df[missing_mask].index:
            filename = df.at[idx, "transcript_file"]
            stem = Path(filename).stem
            ep = ep_index.get(stem)
            if ep is None:
                continue

            pub_ts = ep.get("datePublished")
            if pub_ts:
                df.at[idx, "date"] = pd.to_datetime(pub_ts, unit="s", utc=True).strftime("%Y-%m-%d")
                df.at[idx, "date_source"] = "podcastindex"

            df.at[idx, "duration_s"] = ep.get("duration")
            df.at[idx, "transcript_url"] = ep.get("transcriptUrl") or (
                ep.get("transcripts", [{}])[0].get("url") if ep.get("transcripts") else None
            )
            persons = ep.get("persons", [])
            df.at[idx, "pi_persons"] = json.dumps(persons) if persons else None
            df.at[idx, "pi_episode_num"] = ep.get("episode")
            df.at[idx, "pi_season_num"] = ep.get("season")
            filled += 1

        still_missing = missing_mask.sum() - filled  # after fill
        print(f"  Filled {filled}/{n_missing} — {n_missing - filled} still unmatched")

        # Brief pause to stay within rate limits
        time.sleep(0.5)

    return df, podcast_summaries


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fill missing publication dates in a dataset CSV using PodcastIndex."
    )
    parser.add_argument("dataset", help="Input dataset CSV (output of build_dataset_v2.py)")
    parser.add_argument("-o", "--output", default="dataset_dated.csv", help="Output CSV path")
    parser.add_argument("--podcast-summary", default="podcast_pi_summary.csv",
                        help="Output CSV with podcast-level PodcastIndex metadata")
    args = parser.parse_args()

    api_key = os.environ.get("PODCASTINDEX_API_KEY")
    api_secret = os.environ.get("PODCASTINDEX_API_SECRET")
    if not api_key or not api_secret:
        print("Error: set PODCASTINDEX_API_KEY and PODCASTINDEX_API_SECRET environment variables.")
        print("Get free keys at https://api.podcastindex.org/")
        sys.exit(1)

    df = pd.read_csv(args.dataset)
    n_missing_before = df["date"].isna().sum()
    print(f"Loaded {len(df)} rows, {n_missing_before} with missing dates.")

    if n_missing_before == 0:
        print("No missing dates — nothing to do.")
        return

    df, summaries = fill_dates(df, api_key, api_secret)

    n_after_pi = df["date"].isna().sum()
    print(f"\nPodcastIndex filled {n_missing_before - n_after_pi}/{n_missing_before}. Still missing: {n_after_pi}")

    df.to_csv(args.output, index=False)
    print(f"Saved {len(df)} rows to {args.output}")

    if summaries:
        pd.DataFrame(summaries).to_csv(args.podcast_summary, index=False)
        print(f"Saved podcast-level summary to {args.podcast_summary}")


if __name__ == "__main__":
    main()
