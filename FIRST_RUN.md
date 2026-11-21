# First run (test only, nothing gets posted)

Do these in order. Stop after step 6 and show me the review queue.

1. Read README.md and desk-template/CLAUDE.md.
2. Run: `py scripts/init_desk.py C:\clipdesk`
3. I do NOT have a streamer picked. Run `py scripts/streams.py --query "gta 6"` and show me the top 10 live Twitch streamers (login, viewers, title) as a numbered list. Ask me to pick one number. Prefer a streamer who shows a webcam with the game running (the react layout needs that).
4. Fill `C:\clipdesk\config\desk.json` with that streamer: login, display name, credit handle `@login`, campaign field "TEST ONLY, not posting". Leave the rest as default.
5. Set CLIP_DESK_HOME=C:\clipdesk and CLIP_DESK_ENCODER=h264_nvenc for this session, run `py scripts/pipeline.py status`, and fix anything it reports. Ollama is at http://localhost:11434 with model qwen2.5:7b-instruct.
6. Find that streamer's most recent GTA VOD (`yt-dlp --flat-playlist --playlist-end 5 https://www.twitch.tv/<login>/videos?filter=archives&sort=time`), then run `py scripts/pipeline.py source <vod url> --login <login>`. Fix every failure you hit (yt-dlp, Whisper on GPU, Ollama, face tracking), re-run `py -m pytest tests -q`, and tell me what you changed.

Rules: this is a local test. Do not post, upload, or log in anywhere. Keep fixes small and commit them on this branch.
