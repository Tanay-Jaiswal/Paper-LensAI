import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))

from synth import ITEMS, make_paper  # noqa: E402

ALL = {k: True for k in ITEMS}
NONE = {k: False for k in ITEMS}


@pytest.fixture
def make_pdf(tmp_path):
    def _make(seed=1, items=None, **kw):
        raw, truth = make_paper(seed, items=items if items is not None else ALL, **kw)
        p = tmp_path / f"paper{seed}.pdf"
        p.write_bytes(raw)
        return p, truth
    return _make
