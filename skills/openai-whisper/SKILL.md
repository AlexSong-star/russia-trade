---
name: openai-whisper
description: Local speech-to-text using faster-whisper (no API key needed).
homepage: https://github.com/SYSTRAN/faster-whisper
metadata: {"clawdbot":{"emoji":"🎙️","requires":{"bins":["python"]},"install":[{"id":"pip","kind":"pip","package":"faster-whisper","bins":["python"],"label":"pip install faster-whisper"}]}}
---

# Whisper (faster-whisper)

Use `faster-whisper` for local speech-to-text transcription. No API key required.

## Environment

Python virtual environment: `/tmp/whisper-venv/`

Activate before use:
```bash
source /tmp/whisper-venv/bin/activate
```

## Quick Start

### Transcribe audio to text
```python
from faster_whisper import WhisperModel

model = WhisperModel("base", device="cpu", compute_type="int8")
segments, info = model.transcribe("audio.mp3", language="zh")
for segment in segments:
    print(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")
```

### Output to file
```python
from faster_whisper import WhisperModel

model = WhisperModel("medium", device="cpu", compute_type="int8")
segments, _ = model.transcribe("audio.m4a", language="auto")
with open("output.txt", "w") as f:
    for seg in segments:
        f.write(seg.text + "\n")
```

## Model Options

| Model | Size | Speed | Accuracy |
|-------|------|-------|----------|
| tiny | ~75 MB | Fastest | Lower |
| base | ~150 MB | Fast | Good |
| small | ~500 MB | Medium | Better |
| medium | ~1.5 GB | Slow | High |
| large | ~3 GB | Slowest | Highest |

For Russian trade context: use **medium** or **small** for best Russian language accuracy.

## Supported Formats

`.mp3`, `.m4a`, `.wav`, `.ogg`, `.flac`, `.webm`

## Notes

- First run downloads model files (~75MB - 3GB depending on model size)
- Models are cached in `~/.cache/huggingface/`
- Use `language="auto"` for automatic language detection
- For Russian + Chinese mixed audio: `language="zh"` then process separately
