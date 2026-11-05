from paperlens.ingest import canonical_section, parse_pdf


def test_sections_and_pages(make_pdf):
    p, truth = make_pdf(1)
    doc = parse_pdf(p)
    secs = {s.section for s in doc.sentences}
    assert {"abstract", "introduction", "method", "experiments", "results", "conclusion", "references"} <= secs
    assert doc.n_pages == truth.n_pages
    assert truth.method in doc.title or truth.title.split(":")[0] in doc.title


def test_tables_become_rows_and_stay_out_of_prose(make_pdf):
    p, _ = make_pdf(2, unsupported=0)
    doc = parse_pdf(p)
    rows = [s for s in doc.sentences if s.kind == "table"]
    assert rows and all(r.text.startswith("Table row:") for r in rows)
    assert not any(s.kind == "text" and "Method" in s.text.split()[:2] for s in doc.sentences)


def test_canonical_section_variants():
    assert canonical_section("3.1 Experimental Setup") == "experiments"
    assert canonical_section("RESULTS AND DISCUSSION") == "results"
    assert canonical_section("Our Awesome Idea") is None


def test_blank_pdf_warns(tmp_path):
    import pymupdf
    pdf = pymupdf.open(); pdf.new_page(); p = tmp_path / "b.pdf"; pdf.save(p)
    doc = parse_pdf(p)
    assert any("scanned" in w.lower() or "little" in w.lower() for w in doc.warnings)
