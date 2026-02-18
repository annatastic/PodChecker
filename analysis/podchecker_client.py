"""
PodChecker client for analyzing podcast episodes.

Supports two modes:
- HTTP mode: Calls the Flask backend API (requires backend to be running)
- Local mode: Directly invokes backend processing functions (faster, no server needed)
"""

import os
import re
import sys
import time
import requests
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

# Add backend to path for local mode
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'site', 'backend'))

from .rss_utils import Episode

# Default data directory for caching downloaded audio
DEFAULT_DATA_DIR = Path(__file__).parent.parent / "data"


def sanitize_filename(name: str, max_length: int = 100) -> str:
    """
    Sanitize a string for use as a filename.

    Args:
        name: The string to sanitize
        max_length: Maximum length of the resulting filename

    Returns:
        A safe filename string
    """
    # Replace problematic characters with underscores
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    # Replace multiple spaces/underscores with single underscore
    safe = re.sub(r'[\s_]+', '_', safe)
    # Remove leading/trailing underscores and dots
    safe = safe.strip('_.')
    # Truncate to max length
    if len(safe) > max_length:
        safe = safe[:max_length].rstrip('_')
    return safe or "unnamed"


@dataclass
class AnalysisResult:
    """Result of analyzing a podcast episode."""
    task_id: str
    status: str  # 'done', 'error', 'processing'
    data: list[dict]  # List of fact-check results
    metadata: dict
    error: Optional[str] = None


def download_audio(url: str, output_path: str) -> str:
    """
    Download audio file from URL.

    Args:
        url: URL to download audio from
        output_path: Local path to save the file

    Returns:
        The output_path where file was saved
    """
    response = requests.get(url, stream=True)
    response.raise_for_status()

    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    return output_path


class PodCheckerClient:
    """
    Client for PodChecker fact-checking analysis.

    Can operate in HTTP mode (calling the Flask API) or local mode
    (directly invoking backend functions).
    """

    def __init__(
        self,
        openai_api_key: str,
        perplexity_api_key: str,
        mode: str = "local",
        api_url: str = "http://localhost:8000",
        data_dir: Optional[Path] = None
    ):
        """
        Initialize the PodChecker client.

        Args:
            openai_api_key: OpenAI API key for claim extraction
            perplexity_api_key: Perplexity API key for fact-checking
            mode: "local" for direct function calls, "http" for API calls
            api_url: Base URL for HTTP mode (default: http://localhost:8000)
            data_dir: Directory for caching downloaded audio files
                      (default: <repo>/data/)
        """
        self.openai_api_key = openai_api_key
        self.perplexity_api_key = perplexity_api_key
        self.mode = mode
        self.api_url = api_url
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR

        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)

        if mode == "local":
            # Import backend modules for local mode
            # Need to change to backend directory because api_v3.py loads CSV at module level
            backend_dir = os.path.join(os.path.dirname(__file__), '..', 'site', 'backend')
            original_cwd = os.getcwd()
            try:
                os.chdir(backend_dir)
                from api_v3 import factcheck, process_file
                self._factcheck = factcheck
                self._process_file = process_file
            except ImportError as e:
                raise ImportError(
                    f"Could not import backend modules for local mode: {e}. "
                    "Make sure you're running from the project root or use mode='http'."
                )
            finally:
                os.chdir(original_cwd)

    def analyze_audio_file(self, audio_path: str) -> AnalysisResult:
        """
        Analyze an audio file for factual claims.

        Args:
            audio_path: Path to the audio file

        Returns:
            AnalysisResult with fact-check data
        """
        if self.mode == "http":
            return self._analyze_http(audio_path)
        else:
            return self._analyze_local(audio_path)

    def analyze_episode(
        self,
        episode: Episode,
        podcast_name: str = "podcast"
    ) -> AnalysisResult:
        """
        Analyze a podcast episode by downloading and processing its audio.

        Downloaded audio files are cached in the data directory to avoid
        re-downloading on subsequent runs.

        Args:
            episode: Episode object with audio_url
            podcast_name: Name of the podcast (used for cache filename)

        Returns:
            AnalysisResult with fact-check data
        """
        if not episode.audio_url:
            return AnalysisResult(
                task_id="",
                status="error",
                data=[],
                metadata={},
                error=f"Episode '{episode.title}' has no audio URL"
            )

        # Generate cached filename: <podcast_name>_<episode_title>.mp3
        safe_podcast = sanitize_filename(podcast_name, max_length=50)
        safe_episode = sanitize_filename(episode.title, max_length=100)
        cache_filename = f"{safe_podcast}_{safe_episode}.mp3"
        audio_path = self.data_dir / cache_filename

        # Download if not already cached
        if audio_path.exists():
            print(f"  Using cached audio: {cache_filename}")
        else:
            print(f"  Downloading audio to: {cache_filename}")
            download_audio(episode.audio_url, str(audio_path))

        return self.analyze_audio_file(str(audio_path))

    def _analyze_local(self, audio_path: str) -> AnalysisResult:
        """Analyze using direct backend function calls."""
        import uuid
        from datetime import datetime, timezone

        task_id = str(uuid.uuid4())

        try:
            # Transcribe audio
            transcript = self._process_file(audio_path)

            # Fact-check claims
            df = self._factcheck(transcript, self.openai_api_key, self.perplexity_api_key)

            data = df.to_dict(orient="records")

            return AnalysisResult(
                task_id=task_id,
                status="done",
                data=data,
                metadata={
                    "finished_time": datetime.now(timezone.utc).isoformat(),
                    "file_name": os.path.basename(audio_path),
                    "record_count": len(data),
                    "mode": "local"
                }
            )
        except Exception as e:
            return AnalysisResult(
                task_id=task_id,
                status="error",
                data=[],
                metadata={},
                error=str(e)
            )

    def _analyze_http(self, audio_path: str) -> AnalysisResult:
        """Analyze using HTTP API calls to the Flask backend."""
        # Submit analysis
        task_id = self._submit_analysis_http(audio_path)

        # Poll for result
        return self._poll_for_result_http(task_id)

    def _submit_analysis_http(self, audio_path: str) -> str:
        """Submit audio file to the /analyze endpoint."""
        url = f"{self.api_url}/analyze"

        with open(audio_path, 'rb') as f:
            files = {'file': (Path(audio_path).name, f, 'audio/mpeg')}
            data = {
                'api_key_openai': self.openai_api_key,
                'api_key_perplexity': self.perplexity_api_key
            }
            response = requests.post(url, files=files, data=data)

        response.raise_for_status()
        return response.json()['task_id']

    def _poll_for_result_http(
        self,
        task_id: str,
        poll_interval: int = 10,
        max_wait: int = 600
    ) -> AnalysisResult:
        """Poll the /result endpoint until analysis completes."""
        url = f"{self.api_url}/result/{task_id}"
        elapsed = 0

        while elapsed < max_wait:
            response = requests.get(url)
            response.raise_for_status()
            result = response.json()

            status = result.get('status', 'processing')

            if status == 'done':
                return AnalysisResult(
                    task_id=task_id,
                    status="done",
                    data=result.get('data', []),
                    metadata=result.get('metadata', {})
                )
            elif status == 'error':
                return AnalysisResult(
                    task_id=task_id,
                    status="error",
                    data=[],
                    metadata={},
                    error=result.get('error', 'Unknown error')
                )

            time.sleep(poll_interval)
            elapsed += poll_interval

        return AnalysisResult(
            task_id=task_id,
            status="error",
            data=[],
            metadata={},
            error=f"Analysis did not complete within {max_wait} seconds"
        )
