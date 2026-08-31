from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from config import REPO_ROOT

LINKS_PATH = REPO_ROOT / "sky-links.json"

_LINKS: dict[str, dict[str, str]] | None = None
_BY_ID: dict[str, dict[str, str]] | None = None


def fold_name(name: str) -> str:
    folded = unicodedata.normalize("NFKD", name)
    ascii_name = folded.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")


def load_sky_links(path: Path | None = None) -> dict[str, dict[str, str]]:
    global _LINKS, _BY_ID
    if path is None and _LINKS is not None:
        return _LINKS
    src = path or LINKS_PATH
    raw = json.loads(src.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"sky links must be a mapping: {src}")
    out: dict[str, dict[str, str]] = {}
    by_id: dict[str, dict[str, str]] = {}
    for name, row in raw.items():
        if not isinstance(name, str) or not name:
            raise ValueError(f"sky-links key must be a name: {name!r}")
        if not isinstance(row, dict):
            raise ValueError(f"sky-links[{name!r}] must be a mapping")
        grok = row.get("grokipedia")
        wiki = row.get("wikipedia")
        if not isinstance(grok, str) or not grok:
            raise ValueError(f"sky-links[{name!r}] missing grokipedia URL")
        if not isinstance(wiki, str) or not wiki:
            raise ValueError(f"sky-links[{name!r}] missing wikipedia URL")
        entry = {"grokipedia": grok, "wikipedia": wiki}
        out[name] = entry
        by_id.setdefault(fold_name(name), entry)
    if path is None:
        _LINKS = out
        _BY_ID = by_id
    return out


def sky_entry(name: str, links: dict[str, dict[str, str]] | None = None) -> dict[str, str]:
    table = links if links is not None else load_sky_links()
    if name in table:
        return table[name]
    folded = fold_name(name)
    if links is None and _BY_ID is not None:
        found = _BY_ID.get(folded)
        if found is not None:
            return found
    for key, row in table.items():
        if fold_name(key) == folded:
            return row
    raise KeyError(f"no sky-links entry for {name!r}")
