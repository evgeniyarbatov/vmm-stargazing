from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


def data_dir(override: Path | None = None) -> Path:
    if override is not None:
        return override.expanduser()
    if os.environ.get("DATA_DIR"):
        return Path(os.environ["DATA_DIR"]).expanduser()
    root = os.environ.get("DATA_ROOT", str(Path.home() / "Documents" / "data"))
    return Path(root).expanduser() / "vmm-stargazing"


def load_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or REPO_ROOT / "config.yaml"
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"config is empty or not a mapping: {cfg_path}")
    return raw


def race_window(cfg: dict[str, Any]) -> tuple[datetime, datetime]:
    start = datetime.fromisoformat(str(cfg["start_time"]))
    if start.tzinfo is None:
        raise ValueError("start_time must include a timezone offset")
    if cfg.get("cutoff_time"):
        cutoff = datetime.fromisoformat(str(cfg["cutoff_time"]))
        if cutoff.tzinfo is None:
            raise ValueError("cutoff_time must include a timezone offset")
        return start, cutoff
    hours = cfg.get("time_limit_hours")
    if hours is None:
        raise ValueError("need cutoff_time or time_limit_hours")
    return start, start + timedelta(hours=float(hours))


def resolve_gpx(
    cfg: dict[str, Any],
    datadir: Path,
    gpx_override: Path | None,
    repo_root: Path | None = None,
) -> Path:
    if gpx_override is not None:
        return gpx_override.expanduser()
    rel = Path(str(cfg["gpx"]))
    if rel.is_absolute():
        return rel
    in_repo = (repo_root or REPO_ROOT) / rel
    if in_repo.is_file():
        return in_repo
    return datadir / rel
