# 02-moments
**Does:** download one chunk (default 60 min), transcribe it with faster-whisper on the GPU, score loudness, hype words and chat, write candidates.
**Inputs:** the chunk item from 01. **Tool:** `scripts/moments.py <url> --start-min N`.
**Output:** `output/<job>.json` (job folder, candidate count, signals used) and `jobs/<job>/candidates.json`.
**Check:** the VOD's channel must match an allowlist entry, or the chunk is refused.
**Note:** the GPU is busy here. The LLM stage unloads its model after each call so the two never share the 8 GB.
