# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PodChecker is an automated fact-checking companion for podcasts. It ingests podcast audio (via file upload or RSS feed), transcribes it using Whisper, extracts claims using OpenAI, and fact-checks each claim using Perplexity's web search API.

## Development Commands

### Backend (Flask)
```bash
cd site/backend
pip3 install pandas openai openai-whisper perplexityai feedparser requests flask flask-cors
python3 app.py  # Runs on port 8000
```

### Frontend (React + Vite)
```bash
cd site/frontend
npm install
npm run dev    # Runs on port 5173
npm run build  # TypeScript compile + Vite build
npm run lint   # ESLint
```

### System Dependencies
- ffmpeg (required for Whisper audio processing)

## Architecture

### Backend (`site/backend/`)
- **app.py**: Flask server with REST endpoints. Handles file uploads, task management via threading, and result storage as JSON files in `outputs/`.
- **api_v3.py**: Core processing pipeline:
  1. `process_file()` / `process_rss()`: Transcribe audio using Whisper (`small.en` model)
  2. `factcheck()`: Extract atomic claims via OpenAI, then fact-check each via Perplexity Sonar with web search
- **filtered_attrs.csv**: Domain reliability ratings (1-6 scale). Sources with label >= 5 are marked as "trusted" with a star prefix in results.

### Frontend (`site/frontend/`)
- React 19 + TypeScript + MUI components
- **Upload**: File upload or RSS URL input, requires OpenAI and Perplexity API keys
- **Results**: DataGrid display of fact-checked claims with verdicts (true/false/misleading/unverifiable) and source URLs

### API Endpoints
- `POST /analyze`: Submit audio file or RSS URL for processing (async, returns task_id)
- `GET /result/<task_id>`: Poll for results (status: processing/done/error)
- `GET /download/<task_id>`: Download results as JSON
- `POST /cancel/<task_id>`: Request task cancellation

### Analysis Module (`analysis/`)
- **rss_utils.py**: RSS parsing and credibility metrics
  - `get_recent_episodes(rss_path, n)`: Get N most recent episodes from RSS file
  - `get_episodes_between_dates(rss_path, start, end)`: Filter episodes by date range
  - `compute_credibility_percentage(results)`: Compute episode credibility (0-100%)
    - true=100%, false=0%, misleading=50%, unverifiable=excluded
- **podchecker_client.py**: Unified client for analyzing episodes
  - `PodCheckerClient(openai_key, perplexity_key, mode, api_url, data_dir)`: Main client class
    - `mode="local"`: Direct function calls to backend (faster, no server needed)
    - `mode="http"`: Calls Flask API endpoints (requires backend running)
    - `data_dir`: Cache directory for downloaded audio (default: `<repo>/data/`)
  - `analyze_episode(episode, podcast_name)`: Downloads and analyzes episode, caches audio as `<podcast>_<episode>.mp3`
  - `download_audio(url, output_path)`: Shared utility for downloading episode audio
  - `get_podcast_name(rss_path)`: Extract podcast title from RSS feed
- **episode_credibility_analysis.ipynb**: Example notebook plotting credibility over time
