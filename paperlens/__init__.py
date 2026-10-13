"""PaperLens AI: research evidence and reproducibility auditor."""
__version__ = "1.0.0"

try:  # PyMuPDF prints an advertisement for an optional package on first table search; keep the console clean
    import pymupdf as _pymupdf
    if hasattr(_pymupdf, "no_recommend_layout"):
        _pymupdf.no_recommend_layout()
except Exception:  # pragma: no cover
    pass
