# 06-review (the only human stage)
**Does:** the human skims `queue.md`, approves or rejects. Target: one sitting a day, 10-15 minutes.
**Tool:** `scripts/review.py list | approve | reject --why | posted`.
**Output:** approved clips + caption files in `approved/`. Rejection reasons go to `07-learn/rejections.csv`.
**Claude's job here:** summarise the queue, flag anything the gate could not judge (a spoiler, a tone problem), recommend which to post first. Do not approve for the human.
