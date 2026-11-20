"""Choose which candidate moments become clips, and write title + caption.

Ollama proposes keep/skip + a title. Code enforces the rules, so a weak model cannot break them:
credit and hashtags are added by code, titles are validated, flagged moments are dropped.
Without Ollama it falls back to the top-scoring candidates and no title.
"""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from check import banned_in

SYSTEM = """You help a faceless GTA 6 clip page choose reaction-clip moments from a Twitch streamer's VOD.
You get numbered candidates with timestamps, why each scored, and the transcript line.
Return JSON only: {"clips":[{"n":<int>,"keep":<bool>,"title":"<=60 chars","flags":[]}]}
Rules:
- keep=true only for a clear, self-contained moment: a reaction, surprise, funny or shocking event.
- title describes what happened, in plain words, <=60 characters, no quotation marks, no emojis, no hashtags.
- Never invent a quote, an opinion or a fact that is not in the transcript line.
- flags: add "spoiler" for story reveals, "nsfw" for sexual content, "leak" for unreleased or pirated content, "slur" for hate speech.
- If the transcript line is unclear, keep=false."""

BAD_FLAGS = {"spoiler", "nsfw", "leak", "slur"}


def valid_title(t):
    t = (t or "").strip()
    if not t or len(t) > 70:
        return False
    if re.search(r"[\"“”]|#|http", t):
        return False
    return not banned_in(t)


def build_caption(title, entry, login):
    credit = entry.get("credit") or f"@{login}"
    tags = " ".join(entry.get("hashtags", []))
    parts = [title.strip() if title else f"{entry.get('display', login)} reacts in GTA 6",
             f"Credit: {credit} (twitch.tv/{login})"]
    if tags:
        parts.append(tags)
    return "\n\n".join(parts)


def select(cands, entry, login, cfg, llm_cfg=None, llm_call=None, limit=3):
    """Return (picks, source) where picks = [{n,title,caption,why}] ; source is 'ollama' or 'score-only'."""
    ranked = sorted(cands, key=lambda c: -c["score"])
    answer = None
    if llm_call is not None and ranked:
        lines = [f"streamer: {entry.get('display', login)}"]
        for c in ranked[:limit * 3]:
            lines.append(f"[{c['n']}] {c['start']:.0f}-{c['end']:.0f}s score {c['score']} why: {', '.join(c['why'])} | {c['text'][:300]}")
        answer = llm_call(SYSTEM, "\n".join(lines))
    picks = []
    if answer and isinstance(answer.get("clips"), list):
        by_n = {c["n"]: c for c in ranked}
        for it in answer["clips"]:
            c = by_n.get(it.get("n")) if isinstance(it, dict) else None
            if not c or not it.get("keep"):
                continue
            if BAD_FLAGS & {str(f).lower() for f in (it.get("flags") or [])}:
                continue
            title = it.get("title", "").strip()
            title = title if valid_title(title) else ""
            picks.append({"n": c["n"], "title": title, "caption": build_caption(title, entry, login), "why": c["why"]})
            if len(picks) >= limit:
                break
        return picks, "ollama"
    for c in ranked[:limit]:
        picks.append({"n": c["n"], "title": "", "caption": build_caption("", entry, login), "why": c["why"]})
    return picks, "score-only"
