"""Local run history — stores scores in ~/.repocheck/history.json."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

HISTORY_FILE = Path.home() / ".repocheck" / "history.json"


def _load() -> dict:
    if not HISTORY_FILE.exists():
        return {}
    try:
        return json.loads(HISTORY_FILE.read_text())
    except Exception:
        return {}


def _save(data: dict) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(data, indent=2))


def get_last_run(repo: str) -> Optional[dict]:
    runs = _load().get(repo, [])
    return runs[-1] if runs else None


def save_run(repo: str, score: int, checks: list[dict]) -> None:
    data = _load()
    runs = data.setdefault(repo, [])
    runs.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "score": score,
        "checks": {c["name"]: c["score"] for c in checks},
    })
    data[repo] = runs[-20:]
    _save(data)
