# 01-discover
**Does:** list the newest VODs of each allowlisted streamer, drop old ones and ones whose title is off-topic (`topic_keywords`), and pick the next unprocessed chunk of each.
**Inputs:** `config/desk.json` (allowlist, limits), `state.json` (chunks already done).
**Process:** `pipeline.py run` does this first. Streamers not on the allowlist are never looked at.
**Output:** `output/<timestamp>.json` with the chunk list. `state.json` advances only after a chunk is fully processed.
**Check:** the allowlist is the only source of streamers. Empty allowlist means nothing happens, on purpose.
