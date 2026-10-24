"""Thumbs up / down on individual findings, stored next to the analysis on this computer.

Each vote is kept in `<store>/<analysis id>/feedback.json` and is never sent anywhere. A vote records the finding's id
(for example `claim:C3`), the finding's text at the time of the vote and the PaperLens version, because ids are
re-numbered when a later version finds different claims or gaps: the stored text says what was actually judged.

Votes are reader opinions, not labels: they say whether one person found a finding useful, not whether it is correct.
The blinded labelling sheet (eval/labelling) is the tool for measuring correctness.
"""
from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from . import __version__

KINDS = ("claim", "evidence", "gap", "repro", "number", "revision", "reference", "scorecard")
TARGET_RE = re.compile(r"^(" + "|".join(KINDS) + r"):[A-Za-z0-9_.\-]{1,64}$")
VOTES = ("up", "down")
MAX_NOTE = 1000
MAX_TEXT = 600
FILE = "feedback.json"


def _read(d: Path) -> dict:
    f = d / FILE
    if not f.exists():
        return {}
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except ValueError:          # a damaged file must not break the analysis page
        return {}


def load(d: Path) -> dict:
    """{target: {"vote", "note", "text", "version", "at"}} for one analysis folder."""
    return _read(d)


def record(d: Path, target: str, vote: str | None, note: str = "", text: str = "") -> dict:
    """Store or clear (vote None or "clear") one vote; returns the folder's votes after the change."""
    if not TARGET_RE.match(target or ""):
        raise ValueError(f"invalid finding id {target!r}")
    if vote not in VOTES + ("clear", None):
        raise ValueError("vote must be 'up', 'down' or 'clear'")
    data = _read(d)
    if vote in ("clear", None):
        data.pop(target, None)
    else:
        data[target] = {"vote": vote, "note": (note or "")[:MAX_NOTE], "text": (text or "")[:MAX_TEXT],
                        "version": __version__, "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    tmp = d / (FILE + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(d / FILE)       # write-then-rename: a crash never leaves half a file
    return data


def summary(data: dict) -> dict:
    out = {"up": 0, "down": 0, "by_kind": {}}
    for target, v in data.items():
        kind = target.split(":", 1)[0]
        k = out["by_kind"].setdefault(kind, {"up": 0, "down": 0})
        if v.get("vote") in VOTES:
            out[v["vote"]] += 1
            k[v["vote"]] += 1
    return out


def export_csv(store: Path, only: set | None = None) -> str:
    """Every vote in the store as CSV: one row per vote, with the paper name and the finding text."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["analysis_id", "paper", "finding", "kind", "vote", "note", "finding_text", "version", "at"])
    if store.exists():
        for d in sorted(p for p in store.iterdir() if p.is_dir() and (only is None or p.name in only)):
            data = _read(d)
            if not data:
                continue
            name = (d / "name.txt").read_text(encoding="utf-8") if (d / "name.txt").exists() else ""
            for target, v in sorted(data.items()):
                w.writerow([d.name, name, target, target.split(":", 1)[0], v.get("vote", ""), v.get("note", ""),
                            v.get("text", ""), v.get("version", ""), v.get("at", "")])
    return buf.getvalue()
