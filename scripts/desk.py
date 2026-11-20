"""Desk core: config, creator allowlist, run window, idle check, stage manifests, run lock.

Pure standard library so it can be tested anywhere. Workspace root is CLIP_DESK_HOME (default: current dir).
"""
import copy, json, os, re, sys, time
from datetime import datetime, time as dtime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common
from common import load_json, save_json

STAGES = ["01-discover", "02-moments", "03-pick", "04-cut", "05-gate", "06-review", "07-learn"]

DEFAULTS = {
    "page": {"name": "", "handle": "", "platforms": ["tiktok", "shorts", "reels", "x"]},
    "allowlist": [],  # [{"login","credit","campaign","rules","hashtags":[]}]
    "topic_keywords": ["gta", "grand theft"],  # VOD title must contain one; [] disables the filter
    "limits": {"vods_per_streamer": 2, "chunk_minutes": 60, "max_chunks_per_vod": 6, "max_age_hours": 72,
               "picks_per_chunk": 3, "queue_max": 25, "moments_top": 8},
    "schedule": {"window": "23:00-07:00", "idle_minutes": 10},
    "llm": {"backend": "ollama", "model": "qwen2.5:7b-instruct", "host": "http://localhost:11434",
            "keep_alive": "0", "timeout": 180},
    "cut": {"layout": "react", "title_style": "box", "captions": "bubble", "timeout": 1200},
}


def root():
    return Path(os.environ.get("CLIP_DESK_HOME", Path.cwd()))


def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path=None):
    p = Path(path) if path else root() / "config" / "desk.json"
    if not p.exists():
        sys.exit(f"config not found: {p}. Copy config/desk.example.json to config/desk.json and fill it in "
                 "(or run: python scripts/init_desk.py <folder>).")
    cfg = _merge(DEFAULTS, load_json(p))
    cfg["allowlist"] = [e for e in cfg["allowlist"] if e["login"].lower() != "streamer_login"]  # example placeholder
    for e in cfg["allowlist"]:
        e["login"] = e["login"].lower().lstrip("@")
    return cfg


# ---- allowlist: the only creators this desk may clip ----
def allow_entry(cfg, channel):
    """Return the allowlist entry for a channel/uploader name, or None. Matching ignores case, '@', spaces."""
    norm = lambda s: re.sub(r"[\s@_-]", "", (s or "").lower())
    want = norm(channel)
    if not want:
        return None
    for e in cfg.get("allowlist", []):
        if norm(e["login"]) == want or norm(e.get("display", "")) == want:
            return e
    return None


# ---- run window and idle ----
def parse_window(s):
    if not s or s.lower() in ("always", "any"):
        return None
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*", s)
    if not m:
        raise ValueError(f"bad window {s!r}, use HH:MM-HH:MM (24 h, PC local time)")
    a, b, c, d = map(int, m.groups())
    return dtime(a, b), dtime(c, d)


def in_window(window, now=None):
    w = parse_window(window)
    if w is None:
        return True
    t = (now or datetime.now()).time().replace(second=0, microsecond=0)
    start, end = w
    return start <= t < end if start <= end else (t >= start or t < end)


def idle_seconds():
    """Seconds since the last keyboard/mouse input on Windows; None elsewhere or on failure."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]
        li = LASTINPUTINFO(); li.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li)):
            return None
        return (ctypes.windll.kernel32.GetTickCount() - li.dwTime) / 1000.0
    except Exception:
        return None


def may_run(cfg, now=None, idle=None, ignore_window=False, ignore_idle=False):
    """(ok, reason). Used before the run and between steps, so daytime use of the PC always wins."""
    sch = cfg["schedule"]
    if not ignore_window and not in_window(sch["window"], now):
        return False, f"outside run window {sch['window']}"
    if not ignore_idle:
        idle = idle_seconds() if idle is None else idle
        need = float(sch.get("idle_minutes", 0)) * 60
        if idle is not None and need and idle < need:
            return False, f"PC in use (idle {idle / 60:.0f} min < {need / 60:.0f} min)"
    return True, "ok"


# ---- stage manifests: the hand-off between ICM stages ----
def stage_out(stage):
    d = root() / stage / "output"
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_manifest(stage, key, data):
    save_json(stage_out(stage) / f"{key}.json", data)


def read_manifest(stage, key):
    p = stage_out(stage) / f"{key}.json"
    return load_json(p) if p.exists() else None


def list_manifests(stage):
    return sorted(stage_out(stage).glob("*.json"))


# ---- state (which VOD chunks are done) ----
def state_path():
    return root() / "state.json"


def load_state():
    p = state_path()
    return load_json(p) if p.exists() else {"vods": {}}


def save_state(st):
    save_json(state_path(), st)


# ---- run lock (time-based; os.kill(pid, 0) is unsafe on Windows) ----
class RunLock:
    STALE = 30 * 60

    def __init__(self):
        self.path = root() / ".pipeline.lock"

    def __enter__(self):
        if self.path.exists() and time.time() - self.path.stat().st_mtime < self.STALE:
            sys.exit("another pipeline run is active (lock younger than 30 min): " + str(self.path))
        self.beat()
        return self

    def beat(self):
        self.path.write_text(str(os.getpid()), encoding="utf-8")

    def __exit__(self, *a):
        self.path.unlink(missing_ok=True)
