"""The one human step. Review the queue, approve or reject, log what you posted.

usage:
  python review.py list                       pending clips, newest first
  python review.py approve <id> [<id>...]     copies clip + caption to approved/ ready to post
  python review.py approve --all
  python review.py reject <id> [--why "text"] rejection reasons feed 07-learn (tune the picker)
  python review.py posted <id> --platform tiktok --url <post url>   logs to scoreboard.csv
Nothing is ever uploaded by this tool.
"""
import argparse, csv, shutil, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import desk
from common import load_json, save_json

SCORE_HEADER = ["post_id", "date", "time", "platform", "pillar", "format", "hook", "length_sec", "credit", "views_12h", "views_24h",
                "views_72h", "likes", "reposts_or_shares", "replies_or_comments", "saves_or_bookmarks", "followers_at_read",
                "test_name", "notes"]


def items(status=None):
    out = []
    for f in desk.list_manifests("06-review"):
        d = load_json(f)
        if status is None or d.get("status") == status:
            out.append((f, d))
    return sorted(out, key=lambda x: x[1].get("created", ""), reverse=True)


def write_queue_md():
    lines = ["# Review queue", ""]
    for _, d in items("pending"):
        lines += [f"## {d['id']}", f"clip: {d['clip']}", f"source: {d['source_url']} ({d['start']:.0f}-{d['end']:.0f}s)",
                  f"why picked: {', '.join(d['why'])}", "caption:", "```", d["caption"], "```", ""]
    (desk.root() / "06-review" / "queue.md").write_text("\n".join(lines), encoding="utf-8")


def find(cid):
    for f, d in items():
        if d["id"] == cid:
            return f, d
    sys.exit(f"no queue item {cid}")


def cmd_list(a):
    rows = items("pending")
    print(f"{len(rows)} pending")
    for _, d in rows:
        print(f"{d['id']}  {Path(d['clip']).name}  [{', '.join(d['why'])}]\n    {d['caption'].splitlines()[0]}")
    write_queue_md()


def cmd_approve(a):
    ids = [d["id"] for _, d in items("pending")] if a.all else a.ids
    out = desk.root() / "approved"; out.mkdir(exist_ok=True)
    for cid in ids:
        f, d = find(cid)
        dst = out / f"{cid}.mp4"
        shutil.copy2(d["clip"], dst)
        (out / f"{cid}.caption.txt").write_text(d["caption"], encoding="utf-8")
        d["status"] = "approved"; d["approved_at"] = time.strftime("%Y-%m-%d %H:%M"); save_json(f, d)
        print(f"approved -> {dst}")
    write_queue_md()


def cmd_reject(a):
    f, d = find(a.id)
    d["status"] = "rejected"; d["why_rejected"] = a.why; save_json(f, d)
    log = desk.root() / "07-learn" / "rejections.csv"
    log.parent.mkdir(exist_ok=True)
    new = not log.exists()
    with open(log, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["date", "id", "why_picked", "reason"])
        w.writerow([time.strftime("%Y-%m-%d"), d["id"], "|".join(d["why"]), a.why])
    print("rejected")
    write_queue_md()


def cmd_posted(a):
    f, d = find(a.id)
    sb = desk.root() / "scoreboard.csv"
    new = not sb.exists()
    with open(sb, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(SCORE_HEADER)
        row = {"post_id": a.url or d["id"], "date": time.strftime("%Y-%m-%d"), "time": time.strftime("%H:%M"), "platform": a.platform,
               "pillar": "reaction", "format": "react", "hook": d["caption"].splitlines()[0], "credit": d["credit"], "test_name": a.test}
        w.writerow([row.get(c, "") for c in SCORE_HEADER])
    d["status"] = "posted"; save_json(f, d)
    print("logged. Fill the 12/24/72 h numbers in scoreboard.csv with real values only.")


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list").set_defaults(f=cmd_list)
    p = sub.add_parser("approve"); p.add_argument("ids", nargs="*"); p.add_argument("--all", action="store_true"); p.set_defaults(f=cmd_approve)
    p = sub.add_parser("reject"); p.add_argument("id"); p.add_argument("--why", default=""); p.set_defaults(f=cmd_reject)
    p = sub.add_parser("posted"); p.add_argument("id"); p.add_argument("--platform", required=True)
    p.add_argument("--url", default=""); p.add_argument("--test", default=""); p.set_defaults(f=cmd_posted)
    a = ap.parse_args(); a.f(a)


if __name__ == "__main__":
    main()
