---
name: desk-run
description: Run the automated clip pipeline (discover, moments, pick, cut, gate, review queue) for allowlisted Twitch streamers. Use when the user says "run the desk", "process this VOD", "go live on <streamer>", "set up the overnight run", or asks for the status of the pipeline.
---

# Desk run

The pipeline is scripts, not you. Your job: set it up, start it, report, and handle the cases the scripts cannot.

1. Workspace: if there is no `config/desk.json`, run `python "${CLAUDE_PLUGIN_ROOT}/scripts/init_desk.py" <folder>` and ask the human for the allowlist (streamer login, credit handle, campaign or permission). Never add a streamer without a campaign or permission; the allowlist is the legal and platform safety gate.
2. Status: `python "${CLAUDE_PLUGIN_ROOT}/scripts/pipeline.py" status` (allowlist, run window, Ollama up or not, stage counts).
3. One source now: `pipeline.py source <vod-url> --login <name>`. Whole night's work: `pipeline.py run` (add `--overnight` only from the scheduler, it enforces the window and the idle check).
4. Live: `pipeline.py live <login> --minutes 90`. The PC must stay on. This is the only mode that cannot run overnight unattended.
5. Overnight on Windows: `scripts/windows/install_task.ps1` registers the task. Say that the human runs it in PowerShell.
6. Then hand over to `review-queue`. Do not summarise clips you have not looked at in `queue.md`.

Context rule: read the stage's `CONTEXT.md` in the workspace before touching that stage's output.
