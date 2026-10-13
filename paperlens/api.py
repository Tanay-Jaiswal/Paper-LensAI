"""FastAPI service + static web UI."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import threading
from pathlib import Path

import pymupdf
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import __version__
from .compare import compare
from .pipeline import Analysis, analyze_pdf
from .report import to_html, to_markdown

DATA_DIR = Path(os.environ.get("PAPERLENS_DATA", Path(__file__).resolve().parent.parent / "data" / "store"))
WEB_DIR = Path(__file__).resolve().parent.parent / "web"
MAX_BYTES = 25 * 1024 * 1024
ID_RE = re.compile(r"^[a-f0-9]{8,32}$")

app = FastAPI(title="PaperLens AI", version=__version__)


@app.middleware("http")
async def _no_cache_for_ui(request, call_next):
    """The UI files change between versions; never let the browser reuse an old copy."""
    resp = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        resp.headers["Cache-Control"] = "no-cache"
    return resp
_cache: dict[str, Analysis] = {}
_lock = threading.Lock()


def _path(aid: str) -> Path:
    if not ID_RE.match(aid):
        raise HTTPException(400, "Invalid analysis id")
    return DATA_DIR / aid


def _load(aid: str) -> Analysis:
    with _lock:
        if aid in _cache:
            return _cache[aid]
    pdf = _path(aid) / "paper.pdf"
    if not pdf.exists():
        raise HTTPException(404, "Unknown analysis id")
    a = analyze_pdf(pdf, aid)
    a.doc.source_name = (_path(aid) / "name.txt").read_text(encoding="utf-8") if (_path(aid) / "name.txt").exists() else pdf.name
    with _lock:
        _cache[aid] = a
    return a


def _store(raw: bytes, name: str) -> Analysis:
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, "PDF too large (limit 25 MB)")
    if not raw.startswith(b"%PDF"):
        raise HTTPException(400, "Not a PDF file")
    aid = hashlib.sha1(raw).hexdigest()[:16]   # content-addressed: re-uploading the same PDF reuses it
    d = _path(aid)
    if (d / "analysis.json").exists() and aid in _cache:
        return _cache[aid]
    d.mkdir(parents=True, exist_ok=True)
    (d / "paper.pdf").write_bytes(raw)
    (d / "name.txt").write_text(name[:200], encoding="utf-8")
    try:
        a = analyze_pdf(d / "paper.pdf", aid)
    except Exception as e:  # corrupt / encrypted PDFs
        why = "it is password-protected" if "encrypted" in str(e) else "the file is damaged or not a valid PDF"
        raise HTTPException(422, f"Could not read this PDF: {why} ({e})")
    a.doc.source_name = name
    (d / "analysis.json").write_text(json.dumps(a.to_dict(), ensure_ascii=False), encoding="utf-8")
    with _lock:
        _cache[aid] = a
    return a


def _payload(a: Analysis) -> dict:
    d = a.to_dict()
    d["id"] = a.doc.doc_id
    return d


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...)):
    raw = await file.read()
    return _payload(_store(raw, file.filename or "paper.pdf"))


@app.get("/api/analyses")
def list_analyses():
    out = []
    if DATA_DIR.exists():
        for d in sorted(DATA_DIR.iterdir(), key=lambda p: -p.stat().st_mtime):
            f = d / "analysis.json"
            if f.exists():
                try:
                    j = json.loads(f.read_text(encoding="utf-8"))
                    out.append({"id": d.name, "title": j["document"]["title"], "name": j["document"]["source_name"],
                                "repro": j["reproducibility"]["score"], "claims": j["ledger_stats"]["n_claims"]})
                except (ValueError, KeyError, TypeError):   # a damaged or older stored result must not break the list
                    continue
    return out[:50]


@app.get("/api/analyses/{aid}")
def get_analysis(aid: str):
    return _payload(_load(aid))


@app.get("/api/analyses/{aid}/page/{page}.png")
def page_image(aid: str, page: int, highlight: str = "", zoom: float = 1.4):
    a = _load(aid)
    if not 1 <= page <= a.doc.n_pages:
        raise HTTPException(404, "No such page")
    with pymupdf.open(_path(aid) / "paper.pdf") as pdf:     # closed on exit: an open handle locks the file on Windows
        return Response(_render_page(pdf[page - 1], a, page, highlight, zoom), media_type="image/png")


def _render_page(pg, a: Analysis, page: int, highlight: str, zoom: float) -> bytes:
    ids = [int(x) for x in highlight.split(",") if x.strip().isdigit()][:12]
    by_id = {s.id: s for s in a.doc.sentences}
    colors = [(1, 0.85, 0.2), (0.4, 0.8, 1), (0.6, 1, 0.5)]
    for n, sid in enumerate(ids):
        s = by_id.get(sid)
        if not s or s.page != page:
            continue
        needle = s.text if len(s.text) <= 110 else s.text[:110]
        rects = pg.search_for(needle) or pg.search_for(s.text[:50])
        if not rects and s.kind == "table":
            last = s.text.rsplit(":", 1)[-1].strip()
            rects = pg.search_for(last)
        for r in rects:
            annot = pg.add_highlight_annot(r)
            annot.set_colors(stroke=colors[n % 3])
            annot.update()
    zoom = max(0.6, min(zoom, 3.0)) if zoom == zoom else 1.4     # zoom=nan falls back to the default
    return pg.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom)).tobytes("png")


@app.get("/api/analyses/{aid}/report.{fmt}")
def report(aid: str, fmt: str):
    a = _load(aid)
    if fmt == "json":
        return JSONResponse(_payload(a), headers={"Content-Disposition": f'attachment; filename="paperlens-{aid}.json"'})
    if fmt == "md":
        return PlainTextResponse(to_markdown(a), media_type="text/markdown",
                                 headers={"Content-Disposition": f'attachment; filename="paperlens-{aid}.md"'})
    if fmt == "html":
        return Response(to_html(a), media_type="text/html")
    raise HTTPException(404, "Unknown format")


class CompareReq(BaseModel):
    a: str
    b: str


@app.post("/api/compare")
def compare_endpoint(req: CompareReq):
    return compare(_load(req.a), _load(req.b))


@app.post("/api/demo")
def demo():
    """Create two synthetic demo papers so the UI can be explored without a PDF."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))
    from synth import make_paper
    good = make_paper(11, items={k: True for k in ["code", "data", "hyper", "seeds", "variance", "stat_test",
                                                   "hardware", "software", "splits", "baselines", "ablation",
                                                   "metrics", "limitations", "license"]}, unsupported=0)[0]
    weak = make_paper(23, items={"hyper": True, "metrics": True}, unsupported=1, add_gaps=("overclaim_sota",))[0]
    a = _store(good, "demo-well-documented.pdf")
    b = _store(weak, "demo-overclaiming.pdf")
    return {"a": a.doc.doc_id, "b": b.doc.doc_id}


@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)


@app.get("/api/health")
def health():
    return {"ok": True, "version": __version__}


if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @app.get("/")
    def index():
        return FileResponse(WEB_DIR / "index.html")
