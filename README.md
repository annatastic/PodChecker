# PodChecker

## Overview

PodChecker is a user-facing automated fact-checking companion for podcasts. It ingests podcast episode audio and uses LLMs to extract and fact-check the claims made within. This tool provides claim-level factuality assessments with supporting source URLs as well as an aggregated overview.

![PodChecker system flowchart](systemflowchart2.png)

## Quickstart

### 1. Installation

pip3 install pandas install openai
pip3 install --upgrade pip 
pip install openai-whisper   

download small english model:
https://openaipublic.azureedge.net/main/whisper/models/f953ad0fd29cacd07d5a9eda5624af0f6bcf2258be67c92b79389873d91e0872/small.en.pt

mkdir -p ~/.cache/whisper
mv ~/Downloads/small.en.pt ~/.cache/whisper/

brew install ffmpeg

which ffmpeg
```# add ffmpeg path
import os
os.environ["PATH"] += os.pathsep + "/opt/homebrew/bin"
```

### 2. Run the web app
Run backend:`python3 app.py`

Run frontend: TODO

The application will be available at TODO: url

### 3. Provide input
Paste your OpenAI and Perplexity API keys into the provided fields. Upload an audio file from your computer or paste an RSS feed link to the podcast and hit `submit analysis`

To view a pre-processed example, select a sample report from the `sample report` dropdown. 

