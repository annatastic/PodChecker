"""
PodChecker client for analyzing podcast episodes.

Supports two modes:
- HTTP mode: Calls the Flask backend API (requires backend to be running)
- Local mode: Directly invokes backend processing functions (faster, no server needed)
"""

import json
import os
import re
import sys
import time
import requests
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict

# Add backend to path for local mode
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'site', 'backend'))

from .rss_utils import Episode

# Default data directory for caching downloaded audio and results
DEFAULT_DATA_DIR = Path(__file__).parent.parent / "data"

# Default maximum audio file size in MB
DEFAULT_MAX_AUDIO_SIZE_MB = 60


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


def download_audio(
    url: str,
    output_path: str,
    max_size_mb: Optional[float] = None
) -> tuple[str, bool]:
    """
    Download audio file from URL with optional size limit.

    Args:
        url: URL to download audio from
        output_path: Local path to save the file
        max_size_mb: Maximum file size in MB. If exceeded, download stops early.
                     If None, downloads the entire file.

    Returns:
        Tuple of (output_path, was_truncated) where was_truncated indicates
        if the download was stopped early due to size limit.
    """
    response = requests.get(url, stream=True)
    response.raise_for_status()

    max_bytes = int(max_size_mb * 1024 * 1024) if max_size_mb else None
    downloaded = 0
    was_truncated = False

    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if max_bytes and downloaded + len(chunk) > max_bytes:
                # Write partial chunk up to the limit
                remaining = max_bytes - downloaded
                if remaining > 0:
                    f.write(chunk[:remaining])
                was_truncated = True
                break
            f.write(chunk)
            downloaded += len(chunk)

    return output_path, was_truncated


def download_audio_ffmpeg(url: str, output_path: str, max_duration_seconds: int = 3600) -> str:
    """
    Download and transcode audio from a URL via ffmpeg, limited to max_duration_seconds.

    Unlike download_audio, this handles container formats (MP4/M4A) correctly by
    streaming through ffmpeg rather than truncating raw bytes.
    """
    import subprocess
    cmd = [
        "ffmpeg", "-nostdin",
        "-t", str(max_duration_seconds),
        "-i", url,
        "-acodec", "libmp3lame", "-q:a", "4",
        "-y", output_path,
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr.decode()}")
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
        data_dir: Optional[Path] = None,
        max_audio_size_mb: float = DEFAULT_MAX_AUDIO_SIZE_MB
    ):
        """
        Initialize the PodChecker client.

        Args:
            openai_api_key: OpenAI API key for claim extraction
            perplexity_api_key: Perplexity API key for fact-checking
            mode: "local" for direct function calls, "http" for API calls
            api_url: Base URL for HTTP mode (default: http://localhost:8000)
            data_dir: Directory for caching downloaded audio and results
                      (default: <repo>/data/)
            max_audio_size_mb: Maximum audio file size to download in MB.
                               Downloads are truncated at this size. (default: 60)
        """
        self.openai_api_key = openai_api_key
        self.perplexity_api_key = perplexity_api_key
        self.mode = mode
        self.api_url = api_url
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
        self.max_audio_size_mb = max_audio_size_mb

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
        podcast_name: str = "podcast",
        max_audio_size_mb: Optional[float] = None
    ) -> AnalysisResult:
        """
        Analyze a podcast episode by downloading and processing its audio.

        Both audio files and analysis results are cached in the data directory
        to avoid re-downloading and re-analyzing on subsequent runs.

        Args:
            episode: Episode object with audio_url
            podcast_name: Name of the podcast (used for cache filename)
            max_audio_size_mb: Override the client's default max audio size.
                               If None, uses the client's default.

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

        # Generate cached filenames
        safe_podcast = sanitize_filename(podcast_name, max_length=50)
        safe_episode = sanitize_filename(episode.title, max_length=100)
        base_filename = f"{safe_podcast}_{safe_episode}"
        audio_path = self.data_dir / f"{base_filename}.mp3"
        results_path = self.data_dir / f"{base_filename}.json"

        # Check for cached analysis results first
        if results_path.exists():
            print(f"  Using cached results: {base_filename}.json")
            return self._load_cached_result(results_path)

        # Download audio if not already cached
        max_size = max_audio_size_mb if max_audio_size_mb is not None else self.max_audio_size_mb
        if audio_path.exists():
            print(f"  Using cached audio: {base_filename}.mp3")
        else:
            print(f"  Downloading audio to: {base_filename}.mp3 (max {max_size}MB)")
            _, was_truncated = download_audio(
                episode.audio_url,
                str(audio_path),
                max_size_mb=max_size
            )
            if was_truncated:
                print(f"  Download truncated at {max_size}MB")

        # Analyze and cache results
        result = self.analyze_audio_file(str(audio_path))
        self._save_cached_result(results_path, result, audio_path.name)

        return result

    def _load_cached_result(self, results_path: Path) -> AnalysisResult:
        """Load analysis results from cached JSON file."""
        with open(results_path, 'r', encoding='utf-8') as f:
            cached = json.load(f)

        return AnalysisResult(
            task_id=cached.get('task_id', ''),
            status=cached.get('status', 'done'),
            data=cached.get('data', []),
            metadata=cached.get('metadata', {}),
            error=cached.get('error')
        )

    def _save_cached_result(
        self,
        results_path: Path,
        result: AnalysisResult,
        audio_filename: str
    ) -> None:
        """Save analysis results to JSON file for caching."""
        cached = {
            'task_id': result.task_id,
            'status': result.status,
            'data': result.data,
            'metadata': result.metadata,
            'audio_filename': audio_filename,
        }
        if result.error:
            cached['error'] = result.error

        with open(results_path, 'w', encoding='utf-8') as f:
            json.dump(cached, f, ensure_ascii=False, indent=2)

        print(f"  Cached results to: {results_path.name}")

    def _analyze_local(self, audio_path: str) -> AnalysisResult:
        """Analyze using direct backend function calls."""
        import uuid
        from datetime import datetime, timezone

        task_id = str(uuid.uuid4())

        try:
            # Use cached transcript if available (e.g. pre-populated by prepare_data.py)
            transcript_path = Path(audio_path).with_suffix(".txt")
            if transcript_path.exists():
                print(f"  Using cached transcript: {transcript_path.name}")
                transcript = transcript_path.read_text(encoding="utf-8")
            else:
                transcript = self._process_file(audio_path)
                transcript_path.write_text(transcript, encoding="utf-8")

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
