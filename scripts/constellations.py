from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from config import REPO_ROOT, data_dir, load_config
from utils import load_json

CONSTELLATIONS_URL = "https://github.com/evgeniyarbatov/constellations.git"
DATE_LINE = "DATE = datetime.now().date()"
DATE_PATCH = (
    "DATE = datetime.fromisoformat(os.environ[\"CONSTELLATIONS_DATE\"]).date() "
    "if os.environ.get(\"CONSTELLATIONS_DATE\") else datetime.now().date()"
)


def run(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def ensure_clone(src: Path) -> None:
    src.parent.mkdir(parents=True, exist_ok=True)
    if (src / ".git").is_dir():
        run(["git", "-C", str(src), "fetch", "origin"])
        run(["git", "-C", str(src), "checkout", "main"])
        run(["git", "-C", str(src), "reset", "--hard", "origin/main"])
        return
    run(["git", "clone", CONSTELLATIONS_URL, str(src)])


def write_observer_config(src: Path, cfg: dict, nights: dict) -> None:
    race = cfg.get("race") or {}
    observer = nights.get("observer") or {}
    payload = {
        "lat": float(observer.get("lat") or race["default_lat"]),
        "lon": float(observer.get("lon") or race["default_lon"]),
        "elev_m": float(observer.get("elev_m") or race["default_elev_m"]),
        "timezone": str(cfg.get("timezone") or "Asia/Ho_Chi_Minh"),
        "tz_label": "UTC+7",
        "delta_minutes": 10,
    }
    (src / "config.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def patch_date_env(src: Path) -> None:
    path = src / "scripts" / "plot_constellations.py"
    text = path.read_text(encoding="utf-8")
    if "CONSTELLATIONS_DATE" in text:
        return
    if DATE_LINE not in text:
        raise SystemExit(f"cannot patch DATE in {path}")
    path.write_text(text.replace(DATE_LINE, DATE_PATCH, 1), encoding="utf-8")


def copy_plots(src_plots: Path, dest: Path) -> int:
    dest.mkdir(parents=True, exist_ok=True)
    for old in dest.glob("*.png"):
        old.unlink()
    n = 0
    for png in sorted(src_plots.glob("*.png")):
        shutil.copy2(png, dest / png.name)
        n += 1
    return n


def main() -> None:
    parser = argparse.ArgumentParser(description="Clone constellations, plot each VMM night, copy into docs/.")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--site-dir", type=Path, default=None)
    args = parser.parse_args()
    cfg = load_config(args.config)
    datadir = data_dir(args.data_dir)
    site_dir = (args.site_dir or REPO_ROOT / "docs").expanduser()
    nights = load_json(datadir / "nights.json")
    src = datadir / "constellations"
    out = datadir / "constellations-out"
    ensure_clone(src)
    write_observer_config(src, cfg, nights)
    patch_date_env(src)
    run(["make", "install"], cwd=src)
    run(["make", "download", f"DATA_DIR={out}"], cwd=src)
    total = 0
    for night in nights.get("nights") or []:
        nid = int(night["night_id"])
        date = datetime.fromisoformat(night["end"]).date().isoformat()
        env = os.environ.copy()
        env["CONSTELLATIONS_DATE"] = date
        run(["make", "plot", f"DATA_DIR={out}"], cwd=src, env=env)
        n = copy_plots(out / "plots", site_dir / "plots" / "constellations" / f"night{nid}")
        print(f"night {nid} ({date}): {n} plots")
        total += n
    print(f"{total} constellation plots → {site_dir / 'plots' / 'constellations'}")


if __name__ == "__main__":
    main()
