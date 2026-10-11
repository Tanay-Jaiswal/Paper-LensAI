"""Command line: analyze, compare, serve."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .compare import compare
from .pipeline import analyze_pdf
from .report import to_html, to_markdown


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="paperlens", description="Research evidence & reproducibility auditor")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze", help="analyse one PDF")
    a.add_argument("pdf")
    a.add_argument("--out", default="report", help="output directory")
    c = sub.add_parser("compare", help="compare two PDFs")
    c.add_argument("pdf_a")
    c.add_argument("pdf_b")
    c.add_argument("--out", default="report")
    s = sub.add_parser("serve", help="start the web app")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    args = ap.parse_args(argv)

    if args.cmd == "analyze":
        res = analyze_pdf(args.pdf)
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        stem = Path(args.pdf).stem
        (out / f"{stem}.json").write_text(json.dumps(res.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        (out / f"{stem}.md").write_text(to_markdown(res), encoding="utf-8")
        (out / f"{stem}.html").write_text(to_html(res), encoding="utf-8")
        print(f"{res.doc.title}\n  claims: {len(res.claims)}  reproducibility: {res.rubric['score']}/100  "
              f"gaps: {len(res.gaps)}\n  wrote {out}/{stem}.(json|md|html)")
    elif args.cmd == "compare":
        ra, rb = analyze_pdf(args.pdf_a), analyze_pdf(args.pdf_b)
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        cmp = compare(ra, rb)
        (out / "comparison.json").write_text(json.dumps(cmp, indent=2, ensure_ascii=False), encoding="utf-8")
        print("\n".join(cmp["verdict"]))
        print(f"  wrote {out}/comparison.json")
    elif args.cmd == "serve":
        import uvicorn
        uvicorn.run("paperlens.api:app", host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
