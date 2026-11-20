"""Headless clip pipeline. One source in, review-queue entries out. No human step until 06-review.

usage:
  python pipeline.py run [--overnight] [--ignore-window] [--ignore-idle] [--max-jobs N]   discover, then process what is new
  python pipeline.py source <url-or-file> --login <allowlisted login> [--start-min N]       run one source through every stage
  python pipeline.py live <login> [--minutes 90]                                            record live, then process the spike clips
  python pipeline.py status

Stages write a manifest to NN-stage/output/<job>.json and later stages read it, so a crashed or interrupted
run resumes where it stopped. See CLAUDE.md and each stage's CONTEXT.md.
"""
import argparse, json, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import desk, llm, pick
from common import is_url, load_json, save_json, ytdlp_base, ytdlp_json

SCRIPTS = Path(__file__).parent


def py(script, *args, timeout=3600):
    r = subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, args)], text=True, encoding="utf-8",
                       errors="replace", capture_output=True, timeout=timeout, cwd=str(desk.root()))
    return r.returncode, (r.stdout or ""), (r.stderr or "")


def say(msg):
    print(time.strftime("%H:%M:%S ") + msg, flush=True)


# ---------- 01 discover ----------
def vod_list(login, n):
    url = f"https://www.twitch.tv/{login}/videos?filter=archives&sort=time"
    try:
        info = ytdlp_json(url, ["--flat-playlist", "--playlist-end", str(n)])
    except BaseException as ex:  # common.run() exits on failure
        say(f"discover: could not list VODs for {login}: {ex}")
        return []
    return [{"id": e.get("id"), "url": e.get("url") or e.get("webpage_url"), "title": e.get("title") or "",
             "duration": e.get("duration"), "timestamp": e.get("timestamp")} for e in info.get("entries") or [] if e]


def topic_ok(title, kws):
    return not kws or any(k.lower() in title.lower() for k in kws)


def discover(cfg):
    """Return work items [{login, entry, vod_id, url, title, start_min}] for the next chunk of each fresh VOD."""
    st = desk.load_state()
    lim = cfg["limits"]
    items = []
    for entry in cfg["allowlist"]:
        for v in vod_list(entry["login"], lim["vods_per_streamer"]):
            if not v["url"] or not topic_ok(v["title"], cfg["topic_keywords"]):
                continue
            if v["timestamp"] and time.time() - v["timestamp"] > lim["max_age_hours"] * 3600:
                continue
            rec = st["vods"].setdefault(v["id"], {"chunks_done": 0})
            chunk = lim["chunk_minutes"]
            start = rec["chunks_done"] * chunk
            if rec["chunks_done"] >= lim["max_chunks_per_vod"] or (v["duration"] and start >= v["duration"]):
                continue
            items.append({"login": entry["login"], "vod_id": v["id"], "url": v["url"], "title": v["title"], "start_min": start})
    desk.save_state(st)
    desk.write_manifest("01-discover", time.strftime("%Y%m%d-%H%M"), {"items": items})
    return items


# ---------- one source through stages 02-06 ----------
def process_source(src, login, cfg, start_min=0, llm_on=True):
    entry = desk.allow_entry(cfg, login)
    if not entry:
        say(f"REFUSED: {login!r} is not on the allowlist (config/desk.json). Nothing downloaded.")
        return []
    lim = cfg["limits"]
    # 02 moments
    args = [src, "--top", lim["moments_top"], "--max-minutes", lim["chunk_minutes"]]
    if start_min:
        args += ["--start-min", start_min]
    rc, out, err = py("moments.py", *args)
    job = next((ln.split("job:", 1)[1].strip() for ln in out.splitlines() if ln.startswith("job:")), None)
    if rc != 0 or not job:
        say(f"moments failed for {src}: {(err or out)[-300:]}")
        return []
    key = Path(job).name
    c = load_json(Path(job) / "candidates.json")
    desk.write_manifest("02-moments", key, {"job": job, "source": src, "login": entry["login"], "start_min": start_min,
                                           "candidates": len(c["candidates"]), "signals": c["signals"]})
    # the channel in the metadata must match the allowlist entry (guards against a wrong URL for a login)
    chan = (c.get("info") or {}).get("channel") or (c.get("info") or {}).get("uploader") or ""
    if chan and not desk.allow_entry(cfg, chan):
        say(f"REFUSED: source channel {chan!r} is not on the allowlist.")
        return []
    # 03 pick
    lcfg = cfg["llm"]
    call = (lambda s, u: llm.chat_json(lcfg, s, u)) if llm_on and lcfg["backend"] == "ollama" and llm.available(lcfg) else None
    picks, how = pick.select(c["candidates"], entry, entry["login"], cfg, limit=lim["picks_per_chunk"], llm_call=call)
    desk.write_manifest("03-pick", key, {"job": job, "by": how, "picks": picks})
    say(f"{key}: {len(c['candidates'])} candidates, {len(picks)} picked ({how})")
    # 04 cut + 05 gate + 06 review
    queued = []
    for p in picks:
        item = cut_gate_queue(Path(job), key, p, entry, cfg)
        if item:
            queued.append(item)
    return queued


def cut_gate_queue(job, key, p, entry, cfg):
    cc = cfg["cut"]
    n = p["n"]
    args = [job, "--pick", n, "--layout", cc["layout"], "--cam", "auto", "--captions", cc["captions"]]
    if p["title"]:
        args += ["--title", p["title"], "--title-style", cc["title_style"]]
    rc, out, err = py("cut.py", *args, timeout=cc["timeout"])
    cid = f"{key}-{n}"
    clip = job / "edits" / f"clip_{n}.mp4"
    if rc != 0 or not clip.exists():
        reason = (err.strip() or out.strip()).splitlines()[-1][:200] if (err.strip() or out.strip()) else "cut failed"
        desk.write_manifest("04-cut", cid, {"clip": None, "skipped": reason})
        say(f"  {cid}: skipped ({reason})")
        return None
    desk.write_manifest("04-cut", cid, {"clip": str(clip), "pick": p})
    # 05 gate
    cap_file = job / "edits" / f"clip_{n}.caption.txt"
    cap_file.write_text(p["caption"], encoding="utf-8")
    cargs = [clip, "--caption", p["caption"]]
    rules = entry.get("rules")
    if rules and (desk.root() / rules).exists():
        cargs += ["--campaign", desk.root() / rules]
    rc, out, _ = py("check.py", *cargs)
    meta = load_json(clip.with_suffix(".json"))
    chan_ok = bool(desk.allow_entry(cfg, meta.get("source_channel") or entry["login"]))
    credit_ok = (entry.get("credit") or "@" + entry["login"]).lower() in p["caption"].lower()
    passed = rc == 0 and chan_ok and credit_ok
    desk.write_manifest("05-gate", cid, {"clip": str(clip), "passed": passed, "allowlisted": chan_ok, "credit_in_caption": credit_ok,
                                        "check": out.strip().splitlines()})
    if not passed:
        say(f"  {cid}: gate FAIL")
        return None
    q = {"id": cid, "clip": str(clip), "caption": p["caption"], "credit": entry.get("credit") or "@" + entry["login"],
         "source_url": meta.get("source_url"), "start": meta.get("start"), "end": meta.get("end"), "why": p["why"],
         "campaign": entry.get("campaign"), "status": "pending", "created": time.strftime("%Y-%m-%d %H:%M")}
    desk.write_manifest("06-review", cid, q)
    say(f"  {cid}: queued")
    return q


def pending_count():
    n = 0
    for f in desk.list_manifests("06-review"):
        if load_json(f).get("status") == "pending":
            n += 1
    return n


# ---------- commands ----------
def cmd_run(a):
    cfg = desk.load_config(a.config)
    ok, why = desk.may_run(cfg, ignore_window=a.ignore_window or not a.overnight, ignore_idle=a.ignore_idle or not a.overnight)
    if not ok:
        say(f"not starting: {why}")
        return
    with desk.RunLock() as lock:
        items = discover(cfg)
        say(f"discover: {len(items)} chunk(s) to process")
        done = 0
        for it in items:
            if a.max_jobs and done >= a.max_jobs:
                break
            if pending_count() >= cfg["limits"]["queue_max"]:
                say("review queue is full, stopping. Run review.py to clear it.")
                break
            ok, why = desk.may_run(cfg, ignore_window=a.ignore_window or not a.overnight, ignore_idle=a.ignore_idle or not a.overnight)
            if not ok:
                say(f"stopping: {why}")
                break
            lock.beat()
            process_source(it["url"], it["login"], cfg, it["start_min"])
            st = desk.load_state(); st["vods"][it["vod_id"]]["chunks_done"] += 1; desk.save_state(st)
            done += 1
        say(f"finished: {done} chunk(s), {pending_count()} clip(s) waiting for review")


def cmd_source(a):
    cfg = desk.load_config(a.config)
    q = process_source(a.src, a.login, cfg, a.start_min, llm_on=not a.no_llm)
    say(f"{len(q)} clip(s) queued")


def cmd_live(a):
    cfg = desk.load_config(a.config)
    if not desk.allow_entry(cfg, a.login):
        sys.exit(f"{a.login!r} is not on the allowlist")
    rc, out, err = py("live.py", f"https://twitch.tv/{a.login}", "--minutes", a.minutes, timeout=int(a.minutes * 60 + 600))
    print(out[-800:])
    from common import job_dir
    ld = job_dir(f"https://twitch.tv/{a.login}") / "live"
    for f in sorted(ld.glob("spike_*.mp4")):
        process_source(str(f), a.login, cfg, llm_on=not a.no_llm)


def cmd_status(a):
    cfg = desk.load_config(a.config)
    ok, why = desk.may_run(cfg)
    print(f"allowlist: {', '.join(e['login'] for e in cfg['allowlist']) or '(empty)'}")
    print(f"run window {cfg['schedule']['window']}: {'can run now' if ok else why}")
    print(f"llm: {cfg['llm']['backend']} {cfg['llm']['model']} -> {'up' if llm.available(cfg['llm']) else 'NOT available (score-only fallback)'}")
    for s in desk.STAGES:
        print(f"{s}: {len(list(desk.stage_out(s).glob('*.json')))} item(s)")
    print(f"waiting for review: {pending_count()}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--overnight", action="store_true"); r.add_argument("--ignore-window", action="store_true")
    r.add_argument("--ignore-idle", action="store_true"); r.add_argument("--max-jobs", type=int, default=0); r.set_defaults(f=cmd_run)
    s = sub.add_parser("source"); s.add_argument("src"); s.add_argument("--login", required=True)
    s.add_argument("--start-min", type=int, default=0); s.add_argument("--no-llm", action="store_true"); s.set_defaults(f=cmd_source)
    l = sub.add_parser("live"); l.add_argument("login"); l.add_argument("--minutes", type=float, default=90)
    l.add_argument("--no-llm", action="store_true"); l.set_defaults(f=cmd_live)
    t = sub.add_parser("status"); t.set_defaults(f=cmd_status)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
