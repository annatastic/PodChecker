"""
Utility functions for parsing podcast RSS feeds and computing credibility metrics.
"""

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional, Union
from dataclasses import dataclass
import urllib.request


def _parse_rss_tree(rss_source: str) -> ET.Element:
    """
    Parse an RSS source (file path or URL) into an ElementTree root.
    """
    if rss_source.startswith("http://") or rss_source.startswith("https://"):
        with urllib.request.urlopen(rss_source) as response:
            content = response.read()
        return ET.fromstring(content)
    else:
        return ET.parse(rss_source).getroot()


@dataclass
class Episode:
    """Represents a podcast episode from an RSS feed."""
    title: str
    description: str
    pub_date: datetime
    episode_number: Optional[int]
    audio_url: Optional[str]
    duration: Optional[int]  # in seconds


def get_podcast_name(rss_source: str) -> str:
    """
    Extract the podcast name from an RSS feed (file path or URL).

    Args:
        rss_source: Path to the RSS XML file, or a URL

    Returns:
        The podcast title, or "podcast" if not found
    """
    root = _parse_rss_tree(rss_source)

    # Try to find the channel title
    channel = root.find('.//channel')
    if channel is not None:
        title_elem = channel.find('title')
        if title_elem is not None and title_elem.text:
            return title_elem.text.strip()

    return "podcast"


def parse_rss_file(rss_source: str) -> list[Episode]:
    """
    Parse a podcast RSS feed (file path or URL) and return all episodes.

    Args:
        rss_source: Path to the RSS XML file, or a URL

    Returns:
        List of Episode objects sorted by publication date (newest first)
    """
    root = _parse_rss_tree(rss_source)

    # Define namespaces used in podcast RSS feeds
    namespaces = {
        'itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd',
        'content': 'http://purl.org/rss/1.0/modules/content/',
    }

    episodes = []

    for item in root.findall('.//item'):
        # Get title
        title_elem = item.find('title')
        title = title_elem.text if title_elem is not None else ""

        # Get description
        desc_elem = item.find('description')
        description = desc_elem.text if desc_elem is not None else ""

        # Get publication date
        pub_date_elem = item.find('pubDate')
        if pub_date_elem is not None and pub_date_elem.text:
            pub_date = parsedate_to_datetime(pub_date_elem.text)
        else:
            pub_date = datetime.min.replace(tzinfo=timezone.utc)

        # Get episode number (iTunes namespace)
        episode_num_elem = item.find('itunes:episode', namespaces)
        episode_number = int(episode_num_elem.text) if episode_num_elem is not None and episode_num_elem.text else None

        # Get audio URL from enclosure
        enclosure_elem = item.find('enclosure')
        audio_url = enclosure_elem.get('url') if enclosure_elem is not None else None

        # Get duration (iTunes namespace)
        duration_elem = item.find('itunes:duration', namespaces)
        duration = None
        if duration_elem is not None and duration_elem.text:
            try:
                duration = int(duration_elem.text)
            except ValueError:
                # Duration might be in HH:MM:SS format
                parts = duration_elem.text.split(':')
                if len(parts) == 3:
                    duration = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                elif len(parts) == 2:
                    duration = int(parts[0]) * 60 + int(parts[1])

        episodes.append(Episode(
            title=title,
            description=description,
            pub_date=pub_date,
            episode_number=episode_number,
            audio_url=audio_url,
            duration=duration,
        ))

    # Sort by publication date, newest first
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
