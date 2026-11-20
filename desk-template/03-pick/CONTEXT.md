# 03-pick
**Does:** choose up to `picks_per_chunk` moments and write a title. A local Ollama model proposes; code enforces.
**Inputs:** `jobs/<job>/candidates.json`. **Tool:** `scripts/pick.py`.
**Rules enforced in code, not trusted to the model:** titles <=60-70 chars, no quotes/hashtags/links, no banned terms; spoiler/nsfw/leak/slur flags drop the moment; credit and hashtags are appended by code.
**Fallback:** Ollama down means top scores with no title (`by: score-only`). The run continues.
**Output:** `output/<job>.json` with picks and captions.
