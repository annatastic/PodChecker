# PodChecker
User-Facing Automated Fact Checking for Podcasts

`python3 app.py` to run the backend

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
os.environ["PATH"] += os.pathsep + "/opt/homebrew/bin"```
