"""Versioned freeze manifest for an evaluation: code, configuration, procedure documents and raw outputs.

    python -m eval.freeze_manifest write  <folder>/FREEZE_MANIFEST.json <procedure files ...>
    python -m eval.freeze_manifest verify <folder>/FREEZE_MANIFEST.json
    python -m eval.freeze_manifest hash-outputs  <raw folder> <out.json>     # after the frozen run
    python -m eval.freeze_manifest check-outputs <raw folder> <out.json>

`write` records the SHA-256 of every file in paperlens/, eval/*.py, web/, tests/, requirements.txt and .gitignore, plus
the procedure files named on the command line, the Git commit, the package version, the evidence-linking constants and
the installed package versions. It never overwrites a manifest. Unlike eval/freeze.py (kept as it was for the 0.1.0
freeze) it covers the evaluation procedure as well as the application code.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import subprocess
import sys
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _sha(p: Path) -> str:
    # newlines normalised so the hash does not depend on the checkout's line endings
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def frozen_files(extra: list[str]) -> dict[str, str]:
    paths = sorted((ROOT / "paperlens").glob("*.py")) + sorted((ROOT / "eval").glob("*.py"))
    paths += sorted(p for p in (ROOT / "web").glob("*") if p.is_file()) + sorted((ROOT / "tests").glob("*.py"))
    paths += [ROOT / "requirements.txt", ROOT / ".gitignore"] + [(ROOT / e).resolve() for e in extra]
    return {p.relative_to(ROOT).as_posix(): _sha(p) for p in paths}


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def write(path: Path, extra: list[str]) -> int:
    if path.exists():
        print(f"{path} already exists; a freeze is never overwritten")
        return 1
    import paperlens
    from paperlens import claims as C
    constants = {k: getattr(C, k) for k in ("MIN_LEXICAL", "MIN_LEXICAL_WITH_QUANTITY", "MIN_CONTENT_TOKENS", "MAX_NON_PROSE",
                                            "CAPTION_MIN_LEXICAL", "CAPTION_MIN_TOKENS", "RESTATEMENT_JACCARD",
                                            "RESTATEMENT_CONTAINMENT", "CANDIDATES_SCANNED", "CLAIM_ZONE", "EVIDENCE_SECTIONS")}
    rec = {"frozen_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "paperlens_version": paperlens.__version__,
           "git_commit": _git("rev-parse", "HEAD"), "git_branch": _git("branch", "--show-current"),
           "git_worktree_clean_for_frozen_files": _git("status", "--porcelain", "--", "paperlens", "eval", "web", "tests",
                                                       "requirements.txt", ".gitignore") == "",
           "python": sys.version.split()[0],
           "packages": {d.metadata["Name"]: d.version for d in sorted(metadata.distributions(), key=lambda d: d.metadata["Name"].lower())},
           "evidence_linking_constants": constants,
           "procedure_files": [Path(e).as_posix() for e in extra],
           "files": frozen_files(extra)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    print(f"froze {len(rec['files'])} files at {rec['frozen_utc']} (commit {rec['git_commit'][:7]}, version {rec['paperlens_version']})")
    return 0


def verify(path: Path) -> int:
    rec = json.loads(path.read_text(encoding="utf-8"))
    now = frozen_files(rec["procedure_files"])
    changed = sorted(k for k in set(now) | set(rec["files"]) if now.get(k) != rec["files"].get(k))
    from paperlens import claims as C
    consts = sorted(k for k, v in rec["evidence_linking_constants"].items() if getattr(C, k, None) != v)
    print(f"frozen {rec['frozen_utc']} at commit {rec['git_commit'][:7]}: {len(rec['files'])} files, "
          + ("no frozen file has changed" if not changed else "CHANGED: " + ", ".join(changed))
          + ("" if not consts else "; CONSTANTS CHANGED: " + ", ".join(consts)))
    return 1 if changed or consts else 0


def _tree(folder: Path) -> dict[str, str]:
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file()}


def hash_outputs(folder: Path, out: Path) -> int:
    if out.exists():
        print(f"{out} already exists; not overwritten")
        return 1
    rec = {"hashed_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "files": _tree(folder)}
    out.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    print(f"hashed {len(rec['files'])} files under {folder}")
    return 0


def check_outputs(folder: Path, out: Path) -> int:
    rec = json.loads(out.read_text(encoding="utf-8"))
    now = _tree(folder)
    changed = sorted(k for k in set(now) | set(rec["files"]) if now.get(k) != rec["files"].get(k))
    print(f"{len(rec['files'])} recorded files: " + ("all match" if not changed else "CHANGED: " + ", ".join(changed)))
    return 1 if changed else 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) >= 2 and a[0] == "write":
        sys.exit(write(Path(a[1]), a[2:]))
    if len(a) == 2 and a[0] == "verify":
        sys.exit(verify(Path(a[1])))
    if len(a) == 3 and a[0] in ("hash-outputs", "check-outputs"):
        sys.exit({"hash-outputs": hash_outputs, "check-outputs": check_outputs}[a[0]](Path(a[1]), Path(a[2])))
    print(__doc__)
    sys.exit(2)
