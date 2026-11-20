"""Stage hand-off test: fake the heavy steps (download, Whisper, face tracking), run the real gate, queue and review CLI."""
import json, shutil, subprocess, sys
from pathlib import Path
import pytest

SC = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SC))
import desk, pipeline, review

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg needed")


def make_clip(path, seconds=20):
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=blue:s=1080x1920:r=30:d={seconds}",
                    "-f", "lavfi", "-i", f"sine=frequency=440:d={seconds}", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", str(path)], check=True)


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("CLIP_DESK_HOME", str(tmp_path))
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "desk.json").write_text(json.dumps({"allowlist": [
        {"login": "streamer", "credit": "@streamer", "hashtags": ["#gta6"]}]}))
    (tmp_path / "campaigns.md").write_text("min_seconds: 15\nmax_seconds: 60\nrequired_hashtags: #gta6\n")
    return tmp_path


def fake_py(ws, channel="streamer", cut_ok=True):
    def py(script, *args, timeout=3600):
        if script == "moments.py":
            job = ws / "jobs" / "vod-abc"
            job.mkdir(parents=True, exist_ok=True)
            cands = [{"n": 1, "start": 10, "end": 30, "score": 5.0, "why": ["chat spike"], "text": "oh my god"},
                     {"n": 2, "start": 100, "end": 120, "score": 3.0, "why": ["loudness spike"], "text": "wait what"}]
            (job / "candidates.json").write_text(json.dumps({"source": "x.mp4", "info": {"channel": channel, "webpage_url": "https://twitch.tv/videos/1"},
                                                          "duration": 600, "candidates": cands, "signals": {"chat": True}}))
            return 0, f"job: {job}\n2 candidates", ""
        if script == "cut.py":
            job = Path(args[0]); n = args[args.index("--pick") + 1]
            if not cut_ok or n == 2:
                return 1, "", "skipped: no streamer face over gameplay"
            make_clip(job / "edits" / f"clip_{n}.mp4")
            (job / "edits" / f"clip_{n}.json").write_text(json.dumps({"source_url": "https://twitch.tv/videos/1", "start": 10, "end": 30,
                                                                       "source_channel": channel, "hook": "t"}))
            return 0, str(job / "edits" / f"clip_{n}.mp4"), ""
        return pipeline_real_py(script, *args, timeout=timeout)
    return py


pipeline_real_py = pipeline.py


def test_happy_path_queues_one_clip_and_skips_the_other(ws, monkeypatch):
    monkeypatch.setattr(pipeline, "py", fake_py(ws))
    cfg = desk.load_config()
    q = pipeline.process_source("https://twitch.tv/videos/1", "streamer", cfg, llm_on=False)
    assert [x["id"] for x in q] == ["vod-abc-1"]
    assert desk.read_manifest("04-cut", "vod-abc-2")["skipped"].startswith("skipped")
    g = desk.read_manifest("05-gate", "vod-abc-1")
    assert g["passed"] and g["allowlisted"] and g["credit_in_caption"]
    assert pipeline.pending_count() == 1


def test_unlisted_streamer_is_refused_before_anything_runs(ws, monkeypatch):
    called = []
    monkeypatch.setattr(pipeline, "py", lambda *a, **k: called.append(a) or (0, "", ""))
    assert pipeline.process_source("https://twitch.tv/videos/1", "randomguy", desk.load_config(), llm_on=False) == []
    assert called == []


def test_wrong_channel_in_metadata_is_refused(ws, monkeypatch):
    monkeypatch.setattr(pipeline, "py", fake_py(ws, channel="someone_else"))
    assert pipeline.process_source("https://twitch.tv/videos/1", "streamer", desk.load_config(), llm_on=False) == []
    assert desk.list_manifests("03-pick") == []


def test_gate_blocks_missing_campaign_hashtag(ws, monkeypatch):
    (ws / "config" / "desk.json").write_text(json.dumps({"allowlist": [{"login": "streamer", "credit": "@streamer", "rules": "campaigns.md"}]}))
    monkeypatch.setattr(pipeline, "py", fake_py(ws))
    q = pipeline.process_source("https://twitch.tv/videos/1", "streamer", desk.load_config(), llm_on=False)
    assert q == [] and desk.read_manifest("05-gate", "vod-abc-1")["passed"] is False  # caption has no #gta6


def test_review_cli_approve_reject_posted(ws, monkeypatch, capsys):
    monkeypatch.setattr(pipeline, "py", fake_py(ws))
    pipeline.process_source("https://twitch.tv/videos/1", "streamer", desk.load_config(), llm_on=False)
    monkeypatch.setattr(sys, "argv", ["review.py", "approve", "vod-abc-1"]); review.main()
    assert (ws / "approved" / "vod-abc-1.mp4").exists() and "Credit: @streamer" in (ws / "approved" / "vod-abc-1.caption.txt").read_text()
    monkeypatch.setattr(sys, "argv", ["review.py", "posted", "vod-abc-1", "--platform", "tiktok", "--url", "https://t.example/1"]); review.main()
    assert "tiktok" in (ws / "scoreboard.csv").read_text()
    monkeypatch.setattr(sys, "argv", ["review.py", "reject", "vod-abc-1", "--why", "boring"]); review.main()
    assert "boring" in (ws / "07-learn" / "rejections.csv").read_text()
