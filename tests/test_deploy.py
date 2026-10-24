"""Online-deployment settings: shared password, per-browser paper lists, and a container-like file layout."""
import base64
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from paperlens import api

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def hosted(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "DATA_DIR", tmp_path / "store")
    monkeypatch.setattr(api, "HOSTED", True)
    monkeypatch.setattr(api, "PASSWORD", "")
    api._cache.clear()
    return TestClient(api.app)


def test_hosted_lists_only_the_browsers_own_papers(hosted, make_pdf):
    a = hosted.post("/api/analyze", files={"file": ("a.pdf", make_pdf(1)[0].read_bytes())}).json()["id"]
    b = hosted.post("/api/analyze", files={"file": ("b.pdf", make_pdf(2)[0].read_bytes())}).json()["id"]
    assert hosted.get("/api/analyses").json() == []
    assert [r["id"] for r in hosted.get(f"/api/analyses?ids={a}").json()] == [a]
    assert {r["id"] for r in hosted.get(f"/api/analyses?ids={a},{b},../x").json()} == {a, b}
    assert hosted.get("/api/config").json()["hosted"] is True
    hosted.post(f"/api/analyses/{b}/feedback", json={"target": "claim:C1", "vote": "up"})
    assert b not in hosted.get(f"/api/feedback.csv?ids={a}").text
    assert b in hosted.get(f"/api/feedback.csv?ids={b}").text


def test_shared_password(hosted, monkeypatch):
    monkeypatch.setattr(api, "PASSWORD", "s3cret")
    assert hosted.get("/api/health").status_code == 200                 # health check stays open
    r = hosted.get("/")
    assert r.status_code == 401 and "Basic" in r.headers["www-authenticate"]
    bad = base64.b64encode(b"any:wrong").decode()
    assert hosted.get("/api/analyses", headers={"Authorization": f"Basic {bad}"}).status_code == 401
    assert hosted.get("/api/analyses", headers={"Authorization": "Basic !!notbase64"}).status_code == 401
    good = base64.b64encode(b"anyone:s3cret").decode()
    assert hosted.get("/api/analyses", headers={"Authorization": f"Basic {good}"}).status_code == 200


def test_local_install_is_unchanged(tmp_path, monkeypatch, make_pdf):
    monkeypatch.setattr(api, "DATA_DIR", tmp_path / "store")
    monkeypatch.setattr(api, "HOSTED", False)
    monkeypatch.setattr(api, "PASSWORD", "")
    api._cache.clear()
    c = TestClient(api.app)
    c.post("/api/analyze", files={"file": ("a.pdf", make_pdf(1)[0].read_bytes())})
    assert len(c.get("/api/analyses").json()) == 1 and c.get("/api/config").json()["hosted"] is False


def test_container_file_layout_is_enough(tmp_path):
    """Copy exactly what the Dockerfile copies, then start the app from that copy and use it (upload, demo)."""
    app = tmp_path / "app"
    shutil.copytree(ROOT / "paperlens", app / "paperlens", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "web", app / "web")
    (app / "eval").mkdir()
    for f in ("__init__.py", "synth.py"):
        shutil.copy(ROOT / "eval" / f, app / "eval" / f)
    docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY paperlens ./paperlens" in docker and "COPY web ./web" in docker and "eval/synth.py" in docker
    script = (
        "import os, sys\n"
        f"os.environ.update(PAPERLENS_DATA={str(tmp_path / 'data')!r}, PAPERLENS_HOSTED='1')\n"
        "from fastapi.testclient import TestClient\n"
        "from paperlens import api\n"
        "c = TestClient(api.app)\n"
        "assert c.get('/').status_code == 200 and c.get('/static/app.js').status_code == 200\n"
        "d = c.post('/api/demo').json()\n"
        "j = c.get('/api/analyses/' + d['a']).json()\n"
        "assert j['scorecard']['grade'] and c.get('/api/analyses/' + d['a'] + '/scorecard.pdf').content[:4] == b'%PDF'\n"
        "assert c.get('/api/analyses/' + d['a'] + '/benchmark').status_code == 200\n"
        "print('ok', api.HOSTED, api.DATA_DIR)\n")
    r = subprocess.run([sys.executable, "-c", script], cwd=app, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.startswith("ok True") and (tmp_path / "data").exists()
