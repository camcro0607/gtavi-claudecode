"""Local LLM calls through Ollama (http://localhost:11434). No API key, no per-token cost.

Every call returns parsed JSON or None. Callers must work without it (deterministic fallback).
keep_alive "0" unloads the model right after the call so it never holds the 8 GB of VRAM that Whisper needs.
"""
import json, sys


def available(cfg):
    import requests
    try:
        r = requests.get(cfg["host"].rstrip("/") + "/api/tags", timeout=5)
        r.raise_for_status()
        names = [m.get("name", "") for m in r.json().get("models", [])]
        want = cfg["model"]
        return any(n == want or (":" not in want and n.split(":")[0] == want) for n in names)
    except Exception:
        return False


def chat_json(cfg, system, user):
    import requests
    try:
        r = requests.post(cfg["host"].rstrip("/") + "/api/chat", timeout=float(cfg.get("timeout", 180)), json={
            "model": cfg["model"], "stream": False, "format": "json", "keep_alive": cfg.get("keep_alive", "0"),
            "options": {"temperature": 0.3, "num_ctx": 4096},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        r.raise_for_status()
        return parse_json(r.json()["message"]["content"])
    except Exception as ex:
        print(f"llm call failed: {str(ex)[:120]}", file=sys.stderr)
        return None


def parse_json(text):
    """Tolerant: plain JSON, or the first {...} block in the text."""
    try:
        return json.loads(text)
    except Exception:
        pass
    a, b = text.find("{"), text.rfind("}")
    if a != -1 and b > a:
        try:
            return json.loads(text[a:b + 1])
        except Exception:
            return None
    return None
