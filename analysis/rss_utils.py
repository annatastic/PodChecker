"""
Utility functions for parsing podcast RSS feeds and computing credibility metrics.
"""

import feedparser
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass


@dataclass
class Episode:
    """Represents a podcast episode from an RSS feed."""
    title: str
    description: str
    pub_date: datetime
    episode_number: Optional[int]
    audio_url: Optional[str]
    duration: Optional[int]  # in seconds


def _parse_feed(rss_source: str) -> feedparser.FeedParserDict:
    """Parse an RSS source (file path or URL) using feedparser."""
    if rss_source.startswith("http://") or rss_source.startswith("https://"):
        import requests
        response = requests.get(rss_source, headers={"Accept-Encoding": "identity"})
        response.raise_for_status()
        return feedparser.parse(response.content)
    return feedparser.parse(rss_source)


def get_podcast_name(rss_source: str) -> str:
    """
    Extract the podcast name from an RSS feed (file path or URL).

    Args:
        rss_source: Path to the RSS XML file, or a URL

    Returns:
        The podcast title, or "podcast" if not found
    """
    feed = _parse_feed(rss_source)
    return feed.feed.get("title", "podcast").strip()


def parse_rss_file(rss_source: str) -> list[Episode]:
    """
    Parse a podcast RSS feed (file path or URL) and return all episodes.

    Args:
        rss_source: Path to the RSS XML file, or a URL

    Returns:
        List of Episode objects sorted by publication date (newest first)
    """
    feed = _parse_feed(rss_source)
    episodes = []

    for entry in feed.entries:
        title = entry.get("title", "")
        description = entry.get("summary", "")

        # Publication date
        if entry.get("published_parsed"):
            pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        else:
            pub_date = datetime.min.replace(tzinfo=timezone.utc)

        # iTunes episode number
        episode_number = None
        raw_ep = entry.get("itunes_episode")
        if raw_ep:
            try:
                episode_number = int(raw_ep)
            except ValueError:
                pass

        # Audio URL from enclosures
        audio_url = None
        for enc in entry.get("enclosures", []):
            if enc.get("type", "").startswith("audio"):
                audio_url = enc.get("href")
                break
        if audio_url is None and entry.get("enclosures"):
            audio_url = entry["enclosures"][0].get("href")

        # Duration
        duration = None
        raw_dur = entry.get("itunes_duration")
        if raw_dur:
            try:
                duration = int(raw_dur)
            except ValueError:
                parts = str(raw_dur).split(":")
                try:
                    if len(parts) == 3:
                        duration = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                    elif len(parts) == 2:
                        duration = int(parts[0]) * 60 + int(parts[1])
                except ValueError:
                    pass

        episodes.append(Episode(
            title=title,
            description=description,
            pub_date=pub_date,
            episode_number=episode_number,
            audio_url=audio_url,
            duration=duration,
        ))

    episodes.sort(key=lambda e: e.pub_date, reverse=True)
    return episodes


def get_recent_episodes(rss_path: str, n: int) -> list[Episode]:
    """
    Get the N most recent episodes from an RSS feed.

    Args:
        rss_path: Path to the RSS XML file
        n: Number of most recent episodes to retrieve

    Returns:
        List of the N most recent Episode objects
    """
    episodes = parse_rss_file(rss_path)
    return episodes[:n]


def get_episodes_between_dates(
    rss_path: str,
    start_date: datetime,
    end_date: datetime
) -> list[Episode]:
    """
    Get all episodes published between two dates (inclusive).

    Args:
        rss_path: Path to the RSS XML file
        start_date: Start of date range (inclusive)
        end_date: End of date range (inclusive)

    Returns:
        List of Episode objects within the date range, sorted newest first
    """
    episodes = parse_rss_file(rss_path)

    # Make dates timezone-aware if they aren't already
    if start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=timezone.utc)
    if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=timezone.utc)

    # Convert all to UTC for consistent comparison
    start_utc = start_date.astimezone(timezone.utc)
    end_utc = end_date.astimezone(timezone.utc)

    filtered = [
        ep for ep in episodes
        if start_utc <= ep.pub_date.astimezone(timezone.utc) <= end_utc
    ]
    return filtered


def compute_episode_credibility(fact_check_results: list[dict]) -> float:
    """
    Compute the episode credibility score as the average accuracy of claims.

    Scoring:
        - "true": 1.0
        - "false": 0.0
        - "misleading/partially true": 0.5
        - "unverifiable": excluded from calculation

    Args:
        fact_check_results: List of fact-check result dicts with 'label' field.
                           Each dict should have format: {"num": int, "extracted_claim": str, "label": str, "sources": list}

    Returns:
        Credibility score between 0.0 and 1.0, or None if no verifiable claims
    """
    label_scores = {
        "true": 1.0,
        "false": 0.0,
        "misleading/partially true": 0.5,
    }

    scores = []
    for result in fact_check_results:
        label = result.get("label", "").lower().strip()
        if label in label_scores:
            scores.append(label_scores[label])
        # "unverifiable" claims are excluded

    if not scores:
        return None

    return sum(scores) / len(scores)


def compute_credibility_percentage(fact_check_results: list[dict]) -> Optional[float]:
    """
    Compute the episode credibility score as a percentage (0-100).

    Args:
        fact_check_results: List of fact-check result dicts with 'label' field

    Returns:
        Credibility percentage (0-100), or None if no verifiable claims
    """
    score = compute_episode_credibility(fact_check_results)
    if score is None:
        return None
    return score * 100
