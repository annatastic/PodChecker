# PodChecker
## Overview
PodChecker is a user-facing automated fact-checking companion for podcasts. It ingests podcast episode audio and uses LLMs to extract and fact-check the claims made within. This tool provides claim-level factuality assessments with supporting source URLs as well as an aggregated overview.

![PodChecker system flowchart](assets/systemflowchart2.png)

## Quickstart
### 1. Installation

Clone this repository:

```bash
git clone https://github.com/annatastic/PodChecker.git
```

Enter the project directory:

```bash
cd PodChecker
```
### 2. Prerequisites

Make sure the following are installed on your system:

- Python 3.x  
- Node.js and npm  
- ffmpeg (required for audio processing)

### 3. Backend Setup

Navigate to the backend folder:

```bash
cd site/backend
```

Install Python dependencies:

```bash
pip3 install --upgrade pip
pip3 install pandas openai openai-whisper perplexityai feedparser requests
```

Install ffmpeg:

For macOS (Homebrew):

```bash
brew install ffmpeg
```

For Windows:

Download from: https://ffmpeg.org/download.html

For Ubuntu:

```bash
sudo apt install ffmpeg
```

Verify ffmpeg installation:

```bash
which ffmpeg
```

If necessary, add ffmpeg to PATH inside your Python script:

```python
import os
os.environ["PATH"] += os.pathsep + "/opt/homebrew/bin"
```

Run the backend server:

```bash
python3 app.py
```

### 4. Frontend Setup

Open a separate terminal and navigate to the frontend folder:

```bash
cd site/frontend
```

Install Node dependencies:

```bash
npm install
```

Start the frontend development server:

```bash
npm run dev
```

### 5. Access the Application

Once both backend and frontend are running, open your browser and go to:

```
http://localhost:5173
```

The application should now be ready to use.

### 6. Provide input
Paste your OpenAI and Perplexity API keys into the provided fields. Upload an audio file from your computer or paste an RSS feed link to the podcast and hit `submit analysis`

To view a pre-processed example, select a sample report from the `sample report` dropdown. 


## Citation

If you use this code, please include the following citation:

```
@inproceedings{irmetova2026podchecker,
  title={PodChecker: An Interpretable Fact-Checking Companion for Podcasts},
  author={Irmetova, Anna and Liu, Haoran and Teleki, Maria and Carragher, Peter and Zhang, Julie and Caverlee, James},
  year={2026},
}
```

