import json, os, sys
from datetime import datetime
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import desk, llm, pick


def cfg():
    return desk._merge(desk.DEFAULTS, {"allowlist": [{"login": "streamer", "display": "The Streamer", "credit": "@streamer", "hashtags": ["#gta6"]}]})


def test_allowlist_matches_case_and_at():
    c = cfg()
    assert desk.allow_entry(c, "Streamer")
    assert desk.allow_entry(c, "@streamer")
    assert desk.allow_entry(c, "the streamer")
    assert desk.allow_entry(c, "someoneelse") is None
    assert desk.allow_entry(c, "") is None


@pytest.mark.parametrize("hhmm,expect", [("23:30", True), ("02:00", True), ("06:59", True), ("07:00", False), ("12:00", False), ("22:59", False)])
def test_overnight_window_wraps_midnight(hhmm, expect):
    h, m = map(int, hhmm.split(":"))
    assert desk.in_window("23:00-07:00", datetime(2026, 11, 20, h, m)) is expect


def test_daytime_window_and_always():
    assert desk.in_window("09:00-17:00", datetime(2026, 1, 1, 12, 0))
    assert not desk.in_window("09:00-17:00", datetime(2026, 1, 1, 18, 0))
    assert desk.in_window("always")
    with pytest.raises(ValueError):
        desk.parse_window("nonsense")


def test_may_run_idle_gate(monkeypatch):
    monkeypatch.setattr(desk, "idle_seconds", lambda: None)  # do not read the real keyboard/mouse (Windows would)
    c = cfg()
    night = datetime(2026, 11, 20, 1, 0)
    assert desk.may_run(c, now=night, idle=3600)[0]
    ok, why = desk.may_run(c, now=night, idle=60)  # used the PC 1 minute ago
    assert not ok and "in use" in why
    assert desk.may_run(c, now=night, idle=None)[0]  # idle cannot be measured -> does not block
    monkeypatch.setattr(desk, "idle_seconds", lambda: 30.0)  # measured: used the PC 30 s ago
    assert not desk.may_run(c, now=night, idle=None)[0]
    assert not desk.may_run(c, now=datetime(2026, 11, 20, 14, 0), idle=9999)[0]
    assert desk.may_run(c, now=datetime(2026, 11, 20, 14, 0), idle=0, ignore_window=True, ignore_idle=True)[0]


CANDS = [{"n": i, "start": i * 100, "end": i * 100 + 30, "score": s, "why": ["loudness spike"], "text": f"line {i}"}
         for i, s in [(1, 5.0), (2, 9.0), (3, 1.0), (4, 7.0)]]


def entry():
    return cfg()["allowlist"][0]


def test_pick_without_llm_takes_top_scores_and_adds_credit():
    picks, how = pick.select(CANDS, entry(), "streamer", cfg(), limit=2)
    assert how == "score-only" and [p["n"] for p in picks] == [2, 4]
    assert all("Credit: @streamer" in p["caption"] and "#gta6" in p["caption"] for p in picks)


def test_pick_llm_output_is_validated():
    answer = {"clips": [
        {"n": 2, "keep": True, "title": "Streamer cannot believe the chase", "flags": []},
        {"n": 4, "keep": True, "title": 'He says "this is a leak"', "flags": []},        # quotes + banned word -> title dropped, clip kept
        {"n": 1, "keep": True, "title": "Spoiler scene", "flags": ["spoiler"]},          # flagged -> dropped
        {"n": 3, "keep": False, "title": "boring", "flags": []},
        {"n": 99, "keep": True, "title": "unknown candidate", "flags": []},              # not a real candidate
    ]}
    picks, how = pick.select(CANDS, entry(), "streamer", cfg(), limit=3, llm_call=lambda s, u: answer)
    assert how == "ollama"
    assert [p["n"] for p in picks] == [2, 4]
    assert picks[0]["title"] == "Streamer cannot believe the chase"
    assert picks[1]["title"] == ""
    assert all("Credit: @streamer" in p["caption"] for p in picks)  # credit never depends on the model


def test_pick_llm_garbage_falls_back_to_scores():
    picks, how = pick.select(CANDS, entry(), "streamer", cfg(), limit=2, llm_call=lambda s, u: None)
    assert how == "score-only" and len(picks) == 2


def test_llm_parse_json_tolerant():
    assert llm.parse_json('{"a":1}') == {"a": 1}
    assert llm.parse_json('Sure! {"a": 2} hope that helps') == {"a": 2}
    assert llm.parse_json("no json") is None


def test_manifests_roundtrip_and_lock(tmp_path, monkeypatch):
    monkeypatch.setenv("CLIP_DESK_HOME", str(tmp_path))
    desk.write_manifest("06-review", "x-1", {"id": "x-1", "status": "pending"})
    assert desk.read_manifest("06-review", "x-1")["status"] == "pending"
    assert [p.name for p in desk.list_manifests("06-review")] == ["x-1.json"]
    with desk.RunLock():
        with pytest.raises(SystemExit):
            with desk.RunLock():
                pass
    assert not (tmp_path / ".pipeline.lock").exists()
    with desk.RunLock():
        pass
