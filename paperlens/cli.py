"""Command line: analyze, compare, serve."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .compare import compare
from .field import MODES
from .pipeline import Analysis, analyze_pdf
from .report import to_html, to_markdown


class InputError(Exception):
    """A problem with a file the user named; reported as one line, without a traceback."""


def _analyze(pdf: str, mode: str = "auto") -> Analysis:
    p = Path(pdf)
    if not p.is_file():
        raise InputError(f"file not found: {pdf}")
    with p.open("rb") as f:
        if f.read(4) != b"%PDF":
            raise InputError(f"not a PDF file: {pdf}")
    try:
        res = analyze_pdf(p, mode=mode)
    except Exception as e:  # corrupt / encrypted PDFs
        raise InputError(f"could not read {pdf}: {e}") from e
    for w in res.doc.warnings:
        print(f"  warning: {w}", file=sys.stderr)
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="paperlens", description="Research evidence & reproducibility auditor")
    ap.add_argument("--version", action="version", version=f"paperlens {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze", help="analyse one PDF")
    a.add_argument("pdf")
    a.add_argument("--out", default="report", help="output directory")
    a.add_argument("--mode", choices=MODES, default="auto",
                   help="field-specific checks: auto (detect), cse (Computer Science & Engineering) or general")
    c = sub.add_parser("compare", help="compare two PDFs")
    c.add_argument("pdf_a")
    c.add_argument("pdf_b")
    c.add_argument("--out", default="report")
    c.add_argument("--mode", choices=MODES, default="auto", help="as for analyze")
    s = sub.add_parser("serve", help="start the web app")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    args = ap.parse_args(argv)

    try:
        if args.cmd == "analyze":
            res = _analyze(args.pdf, args.mode)
            out = Path(args.out)
            out.mkdir(parents=True, exist_ok=True)
            stem = Path(args.pdf).stem
            (out / f"{stem}.json").write_text(json.dumps(res.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
            (out / f"{stem}.md").write_text(to_markdown(res), encoding="utf-8")
            (out / f"{stem}.html").write_text(to_html(res), encoding="utf-8")
            print(f"{res.doc.title}\n  checks: {res.mode['label']} ({res.mode['reason']})\n"
                  f"  claims: {len(res.claims)}  reproducibility: {res.rubric['score']}/100 "
                  f"({res.rubric['band']})  gaps: {len(res.gaps)}\n  wrote {out}/{stem}.(json|md|html)")
        elif args.cmd == "compare":
            ra, rb = _analyze(args.pdf_a, args.mode), _analyze(args.pdf_b, args.mode)
            out = Path(args.out)
            out.mkdir(parents=True, exist_ok=True)
            cmp = compare(ra, rb)
            (out / "comparison.json").write_text(json.dumps(cmp, indent=2, ensure_ascii=False), encoding="utf-8")
            print("\n".join(cmp["verdict"]))
            print(f"  wrote {out}/comparison.json")
        elif args.cmd == "serve":
            import socket
            import uvicorn
            with socket.socket() as probe:
                if probe.connect_ex((args.host, args.port)) == 0:
                    raise InputError(f"port {args.port} on {args.host} is already in use; "
                                     f"stop the other program or choose another port with --port")
            print(f"PaperLens AI {__version__}: open http://{args.host}:{args.port} in a browser (Ctrl+C stops the server)")
            uvicorn.run("paperlens.api:app", host=args.host, port=args.port)
    except InputError as e:
        print(f"paperlens: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
