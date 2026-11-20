# Clip desk workspace (ICM)

One agent, one stage at a time. The folders are the pipeline; the files are the hand-offs.

## How to work here
1. Read this file, then `config/desk.json`.
2. Find the stage you are in. Read ONLY that stage's `CONTEXT.md`, then its inputs.
3. Do the stage. Write the result to its `output/` folder. Never edit an earlier stage's output; re-run the stage instead.
4. Stop at `06-review`. The human decides. Nothing is ever uploaded by you.

| Stage | Folder | Who does it | Output |
|---|---|---|---|
| 1 | `01-discover` | script | new VOD chunks from allowlisted streamers |
| 2 | `02-moments` | script (download, Whisper, scoring) | candidates per chunk |
| 3 | `03-pick` | Ollama, code-validated | picks with title + caption |
| 4 | `04-cut` | script (ffmpeg) | 1080x1920 clips |
| 5 | `05-gate` | script | pass/fail with reasons |
| 6 | `06-review` | **human** | approved / rejected |
| 7 | `07-learn` | you + human numbers | scoreboard, rejection log, rules |

Run everything: `python scripts/pipeline.py run --overnight`. One source: `python scripts/pipeline.py source <url> --login <name>`.

## Hard rules (never relax)
- Clip only creators on the allowlist in `config/desk.json`. To add one, the human confirms the campaign or permission first.
- Credit the creator in the caption text. No credit burned into the video.
- No leaks, no "play early", no piracy, no GTA Online money or AFK bots, no invented facts, quotes or numbers.
- No spoilers in titles during launch week. Real numbers only in the scoreboard.
- Never auto-upload, never log in to a platform for the human.
