---
name: review-queue
description: Review the clips the pipeline produced overnight and help the human approve or reject them in one sitting. Use for "what's in the queue", "review my clips", "approve these", or the morning routine.
---

# Review queue

Run `python "${CLAUDE_PLUGIN_ROOT}/scripts/review.py" list`, then read `06-review/queue.md`.

For each pending clip give: id, streamer, why it was picked, the caption, and one line on anything the scripts cannot judge (a story spoiler, a bad title, a moment that is not funny). Recommend which 3 to post first and in what order. The human decides:

- Approve: `review.py approve <id> ...` (copies clip + caption to `approved/`).
- Reject with a reason: `review.py reject <id> --why "..."`. Always ask for a reason, it trains the next run.
- After the human posts: `review.py posted <id> --platform <p> --url <post>`. Then `learning-loop` for the 12/24/72 h reads (real numbers only).

Never post, schedule, or log in anywhere for the human. Check each caption credits the creator before recommending it.
