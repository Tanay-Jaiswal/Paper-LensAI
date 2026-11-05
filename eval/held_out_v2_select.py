"""Select and download the papers of the second held-out set by the fixed rules of
eval/results/held_out_v0.2/PROTOCOL.md section 2.

    python -m eval.held_out_v2_select data/held_out_v0.2_papers eval/results/held_out_v0.2

Written and frozen before any listing was requested. It never runs PaperLens: a file is only opened with PyMuPDF to
count pages and to check that the metadata title is printed on pages 1-2. It refuses to run twice (the manifest is
never overwritten). Everything examined, chosen, skipped or failed is written to SELECTION_LOG.json.
"""
from __future__ import annotations

import csv
import datetime
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import pymupdf

UA = {"User-Agent": "PaperLens-eval/0.2 (held-out paper selection; one request every few seconds)"}
MIN_PAGES, MAX_PAGES, MAX_ATTEMPTS, MAX_ARXIV_CANDIDATES = 6, 80, 3, 60
SKIP_TITLE = re.compile(r"^\s*(author correction|publisher correction|correction|erratum|corrigendum|retraction|editorial|"
                        r"comment|reply)\b", re.I)
CC_BY = re.compile(r"creativecommons\.org/licenses/by/\d\.\d/?$", re.I)

ARXIV_CATEGORIES = ["cs.CV", "cond-mat.mtrl-sci", "q-bio.NC", "econ.EM"]
ARXIV_FROM, ARXIV_TO = "202403010000", "202412312359"
ACL_IDS = ["2024.acl-long.150", "2023.emnlp-main.250", "2024.naacl-long.50"]
PLOS = [("PLoS Pathog", "plospathogens"), ("PLoS One", "plosone"), ("PLoS Med", "plosmedicine")]
PLOS_YEAR = 2023
CROSSREF = [("eLife", "2050-084X"), ("Nature Communications", "2041-1723"), ("Geoscientific Model Development", "1991-9603")]
CROSSREF_FROM, CROSSREF_TO = "2023-06-01", "2023-06-30"

LOG: list[dict] = []


def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get(url: str, pause: float = 3.0) -> bytes:
    """GET with up to 3 tries on time-outs and 5xx/429; a 4xx is final. Raises on failure."""
    last = None
    for attempt in range(3):
        time.sleep(pause if attempt == 0 else pause * 3 * attempt)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code < 500 and e.code != 429:
                break
        except Exception as e:  # time-out, connection reset, DNS
            last = f"{type(e).__name__}: {e}"
    raise RuntimeError(f"{last} for {url}")


def norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", re.sub(r"<[^>]+>", "", t).lower()).strip()


def slug(t: str) -> str:
    return "-".join(norm_title(t).split()[:6])


class Known:
    """Papers already used for development or for the first held-out set."""

    def __init__(self):
        self.ids, self.titles, self.shas = set(), set(), set()
        for m in ("data/Papers/MANIFEST.csv", "data/held_out_papers/MANIFEST.csv"):
            for r in csv.DictReader(open(m, encoding="utf-8-sig")):
                self.ids |= {(r.get("identifier") or "").lower(), (r.get("doi") or "").lower()}
                self.titles.add(norm_title(r.get("title") or ""))
                self.shas.add((r.get("sha256") or "").lower())
        self.ids.discard("")

    def metadata_hit(self, cand: dict) -> bool:
        keys = {cand["identifier"].lower(), (cand.get("doi") or "").lower(), re.sub(r"v\d+$", "", cand["identifier"].lower())}
        known_base = {re.sub(r"v\d+$", "", i) for i in self.ids}
        return bool((keys - {""}) & (self.ids | known_base)) or norm_title(cand["title"]) in self.titles


def fetch_pdf(cand: dict, folder: Path, known: Known) -> tuple[str, dict]:
    """Returns (outcome, details). outcome: ok | excluded (take the next under the rule) | failed (no replacement)."""
    errors = []
    for url in cand["pdf_urls"]:
        try:
            raw = get(url)
        except RuntimeError as e:
            errors.append(str(e))
            continue
        if not raw.startswith(b"%PDF-"):
            errors.append(f"not a PDF (starts with {raw[:12]!r}) for {url}")
            continue
        sha = hashlib.sha256(raw).hexdigest()
        if sha in known.shas:
            return "excluded", {"reason": "same file as a development or first held-out paper"}
        try:
            with pymupdf.open(stream=raw, filetype="pdf") as d:
                pages = len(d)
                front = norm_title(" ".join(d[i].get_text() for i in range(min(2, pages))))
        except Exception as e:
            errors.append(f"does not open in PyMuPDF ({type(e).__name__}) for {url}")
            continue
        words = [w for w in norm_title(cand["title"]).split() if len(w) > 2]
        found = sum(w in front for w in words)
        if words and found / len(words) < 0.6:
            errors.append(f"title words found on pages 1-2: {found}/{len(words)} (wrong file?) for {url}")
            continue
        if not MIN_PAGES <= pages <= MAX_PAGES:
            return "excluded", {"reason": f"{pages} pages (allowed {MIN_PAGES}-{MAX_PAGES})"}
        name = f"{cand['prefix']}_{slug(cand['title'])}.pdf"
        (folder / name).write_bytes(raw)
        return "ok", {"filename": name, "pdf_url": url, "pages": pages, "bytes": len(raw), "sha256": sha,
                      "title_words_found_on_p1_2": f"{found}/{len(words)}", "retrieved_utc": now()}
    return "failed", {"errors": errors}


def run_rule(rule: str, text: str, candidates, folder: Path, known: Known, rows: list[dict]):
    """candidates: iterable of dicts in rule order. Takes the first that is not excluded; a failed download ends the rule."""
    entry = {"rule": rule, "rule_text": text, "examined": [], "result": "no candidate satisfied the rule"}
    LOG.append(entry)
    attempts = 0
    try:
        for cand in candidates:
            if SKIP_TITLE.match(cand["title"]):
                entry["examined"].append({"identifier": cand["identifier"], "title": cand["title"], "skipped": "title marks a non-research item"})
                continue
            if known.metadata_hit(cand):
                entry["examined"].append({"identifier": cand["identifier"], "title": cand["title"], "skipped": "already in the development or first held-out set"})
                continue
            attempts += 1
            outcome, info = fetch_pdf(cand, folder, known)
            entry["examined"].append({"identifier": cand["identifier"], "title": cand["title"], "outcome": outcome, **info})
            if outcome == "ok":
                rows.append({"filename": info["filename"], "title": cand["title"], "source": cand["source"],
                             "identifier": cand["identifier"], "doi": cand.get("doi", ""), "license": cand["license"],
                             "license_evidence": cand["license_evidence"], "landing_url": cand["landing_url"],
                             "pdf_url": info["pdf_url"], "retrieved_utc": info["retrieved_utc"], "pages": info["pages"],
                             "bytes": info["bytes"], "sha256": info["sha256"],
                             "title_words_found_on_p1_2": info["title_words_found_on_p1_2"], "selection_rule": f"{rule}: {text}"})
                entry["result"] = f"selected {cand['identifier']}"
                return
            if outcome == "failed":
                entry["result"] = f"download failed for {cand['identifier']}; not replaced"
                return
            if attempts >= MAX_ATTEMPTS:
                entry["result"] = f"{MAX_ATTEMPTS} candidates excluded; rule abandoned"
                return
    except Exception as e:  # the listing itself could not be obtained
        entry["result"] = f"listing failed: {e}"


# ---- A: arXiv -----------------------------------------------------------------------------------------------------

ATOM = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}


def arxiv_candidates(cat: str):
    seen = 0
    for start in range(0, 300, 100):
        q = urllib.parse.quote(f"cat:{cat} AND submittedDate:[{ARXIV_FROM} TO {ARXIV_TO}]")
        feed = ET.fromstring(get(f"http://export.arxiv.org/api/query?search_query={q}&sortBy=submittedDate"
                                 f"&sortOrder=ascending&start={start}&max_results=100"))
        entries = feed.findall("a:entry", ATOM)
        if not entries:
            return
        for e in entries:
            if e.find("x:primary_category", ATOM).get("term") != cat:
                continue
            seen += 1
            if seen > MAX_ARXIV_CANDIDATES:
                return
            vid = e.find("a:id", ATOM).text.rsplit("/abs/", 1)[1]            # e.g. 2403.00012v2
            base = re.sub(r"v\d+$", "", vid)
            oai = get(f"https://oaipmh.arxiv.org/oai?verb=GetRecord&identifier=oai:arXiv.org:{base}&metadataPrefix=arXivRaw").decode("utf-8", "replace")
            lic = re.search(r"<license>\s*([^<\s]+)\s*</license>", oai)
            lic = lic.group(1) if lic else ""
            if lic.rstrip("/") != "http://creativecommons.org/licenses/by/4.0":
                continue
            title = re.sub(r"\s+", " ", e.find("a:title", ATOM).text).strip()
            yield {"identifier": f"arXiv:{vid}", "title": title, "source": "arXiv", "license": lic,
                   "license_evidence": "arXiv OAI-PMH arXivRaw <license>", "landing_url": f"https://arxiv.org/abs/{vid}",
                   "pdf_urls": [f"https://arxiv.org/pdf/{vid}"], "prefix": f"arxiv_{vid}",
                   "submitted": e.find("a:published", ATOM).text}


# ---- B: ACL Anthology ---------------------------------------------------------------------------------------------

def acl_candidates(aid: str):
    bib = get(f"https://aclanthology.org/{aid}.bib").decode("utf-8", "replace")
    m = re.search(r'title\s*=\s*"(.+?)",\s*\n', bib, re.S)
    title = re.sub(r"[{}]", "", re.sub(r"\s+", " ", m.group(1))) if m else aid
    doi = re.search(r'doi\s*=\s*"([^"]+)"', bib)
    yield {"identifier": f"ACL:{aid}", "title": title, "doi": doi.group(1) if doi else "", "source": "ACL Anthology",
           "license": "CC BY 4.0", "license_evidence": "ACL Anthology copyright statement (material from 2016 onward)",
           "landing_url": f"https://aclanthology.org/{aid}/", "pdf_urls": [f"https://aclanthology.org/{aid}.pdf"],
           "prefix": f"acl_{aid}"}


# ---- C: PLOS via Europe PMC ---------------------------------------------------------------------------------------

def plos_candidates(journal: str, site: str):
    q = (f'JOURNAL:"{journal}" AND FIRST_PDATE:[{PLOS_YEAR}-01-01 TO {PLOS_YEAR}-12-31] AND OPEN_ACCESS:y '
         f'AND LICENSE:"cc by" AND PUB_TYPE:"research-article"')
    got, cursor, first_dates = [], "*", []
    for _ in range(10):
        url = ("https://www.ebi.ac.uk/europepmc/webservices/rest/search?format=json&resultType=core&pageSize=100"
               f"&sort={urllib.parse.quote('FIRST_PDATE_D asc')}&cursorMark={urllib.parse.quote(cursor)}&query={urllib.parse.quote(q)}")
        j = json.loads(get(url, pause=1.0))
        res = j.get("resultList", {}).get("result", [])
        for r in res:
            types = [t.lower() for t in (r.get("pubTypeList") or {}).get("pubType", [])]
            if r.get("pmcid") and r.get("firstPublicationDate") and "research-article" in types and (r.get("license") or "").lower() == "cc by":
                got.append(r)
        first_dates = sorted({r["firstPublicationDate"] for r in got})
        nxt = j.get("nextCursorMark")
        # stop once a page has moved past the three earliest dates (enough for MAX_ATTEMPTS candidates in order)
        if not res or not nxt or nxt == cursor or (res and len(first_dates) > 3 and res[-1].get("firstPublicationDate", "") > first_dates[2]):
            break
        cursor = nxt
    got.sort(key=lambda r: (r["firstPublicationDate"], int(r["pmcid"][3:])))
    for r in got:
        doi = r.get("doi", "")
        yield {"identifier": r["pmcid"], "title": re.sub(r"<[^>]+>", "", r.get("title", "")).rstrip("."), "doi": doi,
               "source": "PLOS (article also in PubMed Central OA)", "license": r.get("license", ""),
               "license_evidence": "Europe PMC licence field", "landing_url": f"https://europepmc.org/article/PMC/{r['pmcid']}",
               "pdf_urls": [f"https://europepmc.org/articles/{r['pmcid']}?pdf=render",
                            f"https://journals.plos.org/{site}/article/file?id={doi}&type=printable"],
               "prefix": f"pmc_{r['pmcid']}", "first_publication_date": r["firstPublicationDate"]}


# ---- D: Crossref --------------------------------------------------------------------------------------------------

def _publisher_pdf(doi: str) -> list[str]:
    d = doi.lower()
    if d.startswith("10.1038/"):
        return [f"https://www.nature.com/articles/{doi.split('/', 1)[1]}.pdf"]
    if d.startswith("10.7554/elife."):
        return [f"https://elifesciences.org/articles/{re.sub(r'[^0-9].*$', '', d.split('elife.', 1)[1])}.pdf"]
    m = re.match(r"10\.5194/([a-z]+)-(\d+)-(\d+)-(\d+)$", d)
    if m:
        j, vol, page, year = m.groups()
        return [f"https://{j}.copernicus.org/articles/{vol}/{page}/{year}/{j}-{vol}-{page}-{year}.pdf"]
    return []


def crossref_candidates(journal: str, issn: str):
    url = (f"https://api.crossref.org/journals/{issn}/works?filter=from-pub-date:{CROSSREF_FROM},until-pub-date:{CROSSREF_TO},"
           "type:journal-article&sort=published&order=asc&rows=200&select=DOI,title,published,license,link")
    items = json.loads(get(url, pause=1.0))["message"]["items"]

    def key(it):
        parts = (it.get("published", {}).get("date-parts") or [[9999]])[0]
        return tuple((list(parts) + [1, 1])[:3]), it["DOI"].lower()
    for it in sorted(items, key=key):
        lic = [x.get("URL", "") for x in it.get("license", [])]
        cc = [u for u in lic if CC_BY.search(u)]
        if not cc or not it.get("title"):
            continue
        doi = it["DOI"]
        links = [x["URL"] for x in it.get("link", []) if x.get("content-type") == "application/pdf"]
        yield {"identifier": f"doi:{doi}", "title": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", it["title"][0])).strip(), "doi": doi,
               "source": f"{journal} (Crossref)", "license": cc[0], "license_evidence": "Crossref licence field",
               "landing_url": f"https://doi.org/{doi}", "pdf_urls": list(dict.fromkeys(links + _publisher_pdf(doi))),
               "prefix": "doi_" + re.sub(r"[^A-Za-z0-9.]+", "-", doi), "published": key(it)[0]}


def main(papers: str, results: str) -> int:
    folder, out = Path(papers), Path(results)
    if (folder / "MANIFEST.csv").exists() or (out / "SELECTION_LOG.json").exists():
        print("a manifest or selection log already exists; selection is done once and never repeated")
        return 1
    folder.mkdir(parents=True, exist_ok=True)
    known, rows = Known(), []
    started = now()
    for i, cat in enumerate(ARXIV_CATEGORIES, 1):
        run_rule(f"A{i}", f"first CC BY 4.0 paper with primary category {cat} submitted from 2024-03-01 (arXiv)",
                 arxiv_candidates(cat), folder, known, rows)
    for i, aid in enumerate(ACL_IDS, 1):
        run_rule(f"B{i}", f"ACL Anthology paper {aid}", acl_candidates(aid), folder, known, rows)
    for i, (journal, site) in enumerate(PLOS, 1):
        run_rule(f"C{i}", f"first CC BY research article of {PLOS_YEAR} in {journal} by first publication date, lowest PMCID (Europe PMC)",
                 plos_candidates(journal, site), folder, known, rows)
    for i, (journal, issn) in enumerate(CROSSREF, 1):
        run_rule(f"D{i}", f"first CC BY journal-article of June 2023 in {journal} by publication date, then DOI (Crossref)",
                 crossref_candidates(journal, issn), folder, known, rows)
    if rows:
        with open(folder / "MANIFEST.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader(); w.writerows(rows)
    out.mkdir(parents=True, exist_ok=True)
    (out / "SELECTION_LOG.json").write_text(json.dumps({"started_utc": started, "finished_utc": now(), "planned_candidates": 13,
                                                        "obtained": len(rows), "rules": LOG}, indent=2, ensure_ascii=False), encoding="utf-8")
    for e in LOG:
        print(f"{e['rule']}: {e['result']}  ({len(e['examined'])} examined)")
    print(f"{len(rows)} of 13 planned papers obtained -> {folder}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
