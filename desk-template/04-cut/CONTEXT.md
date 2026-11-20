# 04-cut
**Does:** render each pick as a 1080x1920 react clip (face on top, game below, title on the seam, bubble captions).
**Tool:** `scripts/cut.py` with `--layout react --cam auto`. Encoder: set `CLIP_DESK_ENCODER=h264_nvenc` for the GPU encoder.
**Skips (normal, not errors):** no stable streamer face, or no gameplay outside the cam. The reason is written to the output file.
**Output:** `output/<job>-<n>.json`, clip in `jobs/<job>/edits/`.
