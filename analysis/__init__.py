"""
PodChecker analysis utilities for podcast RSS parsing and credibility metrics.
"""

from .rss_utils import (
    Episode,
    parse_rss_file,
    get_podcast_name,
    get_recent_episodes,
    get_episodes_between_dates,
    compute_episode_credibility,
    compute_credibility_percentage,
)

from .podchecker_client import (
    PodCheckerClient,
    AnalysisResult,
    download_audio,
    sanitize_filename,
    DEFAULT_DATA_DIR,
    DEFAULT_MAX_AUDIO_SIZE_MB,
)

__all__ = [
    # RSS utilities
    "Episode",
    "parse_rss_file",
    "get_podcast_name",
    "get_recent_episodes",
    "get_episodes_between_dates",
    # Credibility metrics
    "compute_episode_credibility",
    "compute_credibility_percentage",
    # Client
    "PodCheckerClient",
    "AnalysisResult",
    "download_audio",
    "sanitize_filename",
    "DEFAULT_DATA_DIR",
    "DEFAULT_MAX_AUDIO_SIZE_MB",
]
