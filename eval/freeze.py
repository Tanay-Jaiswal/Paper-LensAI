"""Record or verify a freeze of the extraction, evidence-linking and scoring code.

    python -m eval.freeze write  eval/results/held_out/FREEZE.json     # before a held-out evaluation
    python -m eval.freeze verify eval/results/held_out/FREEZE.json     # later: has any frozen file changed?

The freeze is a SHA-256 of every file in paperlens/. A held-out result is only valid for the code it was frozen with;
if `verify` reports a change, results produced afterwards must be reported as a separate, later evaluation.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def hashes() -> dict[str, str]:
    # newlines normalised so the hash does not depend on the checkout's line endings
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            for p in sorted((ROOT / "paperlens").glob("*.py"))}


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("write", "verify"):
        print(__doc__)
        return 2
    path = Path(sys.argv[2])
    if sys.argv[1] == "write":
        if path.exists():
            print(f"{path} already exists; a freeze is never overwritten")
            return 1
        path.parent.mkdir(parents=True, exist_ok=True)
        rec = {"frozen_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "files": hashes()}
        path.write_text(json.dumps(rec, indent=2), encoding="utf-8")
        print(f"froze {len(rec['files'])} files at {rec['frozen_utc']}")
        return 0
    rec = json.loads(path.read_text(encoding="utf-8"))
    now = hashes()
    changed = sorted(k for k in set(now) | set(rec["files"]) if now.get(k) != rec["files"].get(k))
    print(f"frozen {rec['frozen_utc']}: " + ("no frozen file has changed" if not changed else "CHANGED: " + ", ".join(changed)))
    return 1 if changed else 0


if __name__ == "__main__":
    sys.exit(main())
