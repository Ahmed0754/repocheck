"""Load and parse .repocheckrc config files."""
from __future__ import annotations

import configparser
from pathlib import Path
from typing import Optional


def load_config(path: Optional[str] = None) -> dict:
    cfg_path = Path(path) if path else Path(".repocheckrc")
    if not cfg_path.exists():
        return {}

    parser = configparser.ConfigParser()
    parser.optionxform = str  # preserve case for check names
    parser.read(cfg_path)

    config: dict = {}

    if "repocheck" in parser:
        section = parser["repocheck"]
        if "skip" in section:
            config["skip"] = [s.strip() for s in section["skip"].split(",") if s.strip()]
        if "min_score" in section:
            config["min_score"] = int(section["min_score"])

    if "weights" in parser:
        config["weights"] = {k: float(v) for k, v in parser["weights"].items()}

    return config
