# 05-gate
**Does:** decide if a clip may reach the human at all.
**Checks:** 1080x1920, ~30 fps, audio, length, campaign rules from the streamer's `rules` file, banned terms, source channel on the allowlist, creator credit present in the caption.
**Tool:** `scripts/check.py` plus the allowlist/credit checks in `pipeline.py`.
**Output:** `output/<job>-<n>.json` with `passed` and the PASS/FAIL lines. A FAIL is never shown to the human.
