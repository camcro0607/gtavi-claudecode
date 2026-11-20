# 07-learn
**Does:** turn rejections and real post numbers into rules for tomorrow.
**Inputs:** `07-learn/rejections.csv`, `scoreboard.csv` (real numbers pasted by the human, never guessed).
**Process:** read the last 7 days. Look for patterns in what was rejected (bad cam, boring, wrong game, title tone) and what over-performed. Write at most 3 rules to `learning.md`; adjust `config/desk.json` limits or the pick prompt only with the human's yes.
**One test per day.** No verdict before 24 h, prefer the 72 h read.
