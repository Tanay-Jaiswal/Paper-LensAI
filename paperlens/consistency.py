"""Numeric Consistency Audit: recompute the arithmetic a paper states about its own numbers.

A paper often states a number together with the numbers it was computed from: "45 of 120 patients (37.5%)",
"accuracy rose from 81.2 to 84.6 (+3.4 points)", "OR 1.52 (95% CI 1.21-1.90)", "t(28) = 2.20, p = .036".
Each such statement can be checked with a calculator, without understanding the science. This module finds those
statements with fixed patterns, redoes the calculation, and reports every check, consistent or not, with the formula,
the stated value, the recomputed value and the rounding tolerance, so that a reader can redo it by hand.

Rounding is handled generously: a stated value is consistent when it equals the recomputed value rounded *or*
truncated to the number of decimals it is written with, after allowing for the rounding of the inputs. A flag is
therefore a statement that no rounding of the printed inputs gives the printed result, not a guess.

Only `p_value` uses a statistical distribution (via SciPy, as the statcheck tool does for psychology papers); the
other checks are plain arithmetic. Nothing is learned or generated.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .models import Document, Sentence

_MINUS = "−–‒—"   # typographic minus signs and dashes PDFs use for "-"
NUM = r"\d+(?:\.\d+)?"
SNUM = r"[-−–]?\s?\d+(?:\.\d+)?"


@dataclass
class Check:
    id: str
    kind: str                  # a key of KIND_LABEL
    status: str                # consistent | inconsistent | not_reproduced
    severity: str              # high | medium | low ("low" unless inconsistent)
    message: str
    page: int
    sentence_id: int
    section: str
    quote: str                 # the matched statement, verbatim
    formula: str               # how the value was recomputed, in plain arithmetic
    stated: str
    computed: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _f(s: str) -> float:
    s = s.replace(" ", "")
    for ch in _MINUS:
        s = s.replace(ch, "-")
    return float(s)


def _dec(s: str) -> int:
    s = s.strip()
    return len(s.split(".")[1]) if "." in s else 0


def _half(s: str) -> float:
    """Half a unit in the last printed digit: the rounding uncertainty of a printed value."""
    return 0.5 * 10 ** -_dec(s)


def _fmt(x: float, d: int) -> str:
    return f"{x:.{max(d, 1) + 3}f}".rstrip("0").rstrip(".") if abs(x) < 1e6 else f"{x:.4g}"


def _matches_printed(stated: str, lo: float, hi: float) -> bool:
    """Is the printed value a rounding or a truncation of some true value in [lo, hi]?"""
    v, d = abs(_f(stated)), _dec(stated)
    lo, hi = (min(abs(lo), abs(hi)), max(abs(lo), abs(hi))) if lo * hi >= 0 else (0.0, max(abs(lo), abs(hi)))
    step = 10 ** -d
    eps = 1e-9
    rounds = (v - step / 2 - eps) <= hi and (v + step / 2 + eps) >= lo
    truncs = v - eps <= hi and (v + step + eps) >= lo
    return rounds or truncs


def _quote(text: str, m: re.Match, pad: int = 60) -> str:
    a, b = max(0, m.start() - pad), min(len(text), m.end() + pad)
    return ("…" if a else "") + text[a:b].strip() + ("…" if b < len(text) else "")


# ---- 1. percentages of a count: "45 of 120 (37.5%)", "45/120 (37.5%)", "45 (37.5%) of 120" -------------------------
_PCT_A = re.compile(rf"(?<![\w.,])(?P<x>\d{{1,7}})\s*(?:/|of|out of)\s*(?:the\s+|all\s+)?(?P<y>\d{{1,7}})(?![\d.,])"
                    rf"(?:\s+[a-z][a-z\-]*){{0,3}}?\s*[(\[]\s*(?P<p>{NUM})\s*%\s*[)\],;]", re.I)
_PCT_B = re.compile(rf"(?<![\w.,])(?P<x>\d{{1,7}})\s*[(\[]\s*(?P<p>{NUM})\s*%\s*[)\]]\s*(?:of|out of)\s*(?:the\s+|all\s+)?"
                    rf"(?P<y>\d{{1,7}})(?![\d.,])", re.I)


def _percent_checks(s: Sentence):
    seen = set()
    for rx in (_PCT_A, _PCT_B):
        for m in rx.finditer(s.text):
            x, y, p = int(m.group("x")), int(m.group("y")), m.group("p")
            if (m.start("x"), m.group("p")) in seen or y == 0 or x > y or y < 2:
                continue
            seen.add((m.start("x"), m.group("p")))
            if re.fullmatch(r"(19|20)\d\d", m.group("y")) or re.fullmatch(r"(19|20)\d\d", m.group("x")):
                continue    # "in 2019 of ..." is a year, not a count
            comp = 100 * x / y
            ok = _matches_printed(p, comp, comp)
            slip = abs(comp - _f(p)) <= 10 ** -_dec(p) + 1e-9
            yield dict(kind="percent_of_count", ok=ok, m=m, stated=f"{p}%", computed=f"{_fmt(comp, _dec(p))}%",
                       formula=f"{x} / {y} × 100 = {_fmt(comp, _dec(p))}%",
                       msg=(f"{x} of {y} is {_fmt(comp, _dec(p))}%, but the paper prints {p}%"
                            + (" (a rounding slip in the last digit)." if slip else ".")
                            if not ok else f"{x} of {y} = {_fmt(comp, _dec(p))}%, printed as {p}%."),
                       severity="low" if slip else ("high" if abs(comp - _f(p)) >= 1 else "medium"),
                       details={"count": x, "total": y})


# ---- 2. stated changes: "from 81.2 to 84.6 (+3.4)", "reduced by 25% from 40 to 30" -------------------------------
_UNIT = r"(?:\s?%|\s?percent(?:age)?(?:\s+points?)?|\s?(?:percentage\s+)?points?|\s?pp\b|\s?p\.p\.)?"
_FROM_TO = re.compile(rf"\bfrom\s+(?P<a>{SNUM})\s?(?:(?P<ua>%)|[A-Za-zµ]{{1,4}}\b)?\s+(?:to|→)\s+(?P<b>{SNUM})"
                      rf"\s?(?:(?P<ub>%)|[A-Za-zµ]{{1,4}}\b(?!\s+(?:to|→)))?(?!\d|\.\d)")
_CHANGE_WORD = (r"(?:increase|decrease|reduction|improvement|gain|drop|decline|rise|fall|boost|difference|"
                r"change|lift|jump|cut)")
_AMOUNT = rf"(?P<d>{NUM})(?P<u>{_UNIT})"
# the stated difference right after "from A to B": ", an increase of 3.4 points", "(+3.4)", "(3.4% reduction)", ", i.e. by 3.4"
_BY_AFTER = [re.compile(r"^\s*" + x, re.I) for x in (
    rf",?\s*(?:i\.e\.,?\s*|that is,?\s*)?(?:an?\s+)?(?:\w+\s+)?{_CHANGE_WORD}\s+of\s+(?:about\s+|approximately\s+|~\s?)?{_AMOUNT}",
    rf",?\s*(?:i\.e\.,?\s*)?by\s+(?:about\s+|approximately\s+|~\s?|nearly\s+|almost\s+)?{_AMOUNT}",
    rf"[(]\s*[+−\-–]\s?{_AMOUNT}\s*[),;]",
    rf"[(,]\s*(?:an?\s+)?{_AMOUNT}\s+(?:absolute\s+|relative\s+)?{_CHANGE_WORD}",
)]
# ... or before it: "reduced the error by 25% from 40 to 30"
_BY_BEFORE = re.compile(rf"\bby\s+(?:about\s+|approximately\s+|~\s?|nearly\s+|almost\s+)?{_AMOUNT}(?:\s+[A-Za-z\-]+){{0,3}}\s*,?\s*$", re.I)
_YEAR = re.compile(r"(?:19|20)\d\d")
_UP = re.compile(r"\b(increas\w*|ris(?:e|es|ing)|rose|grew|grow\w*|higher|gain\w*|boost\w*|rais\w*|up\b)", re.I)
_DOWN = re.compile(r"\b(decreas\w*|reduc\w*|fell|fall\w*|drop\w*|declin\w*|lower\w*|shrank|shrink\w*|cut\b|down\b|fewer|less)", re.I)
_FOLD = re.compile(rf"(?P<d>{NUM})\s?(?:-|\s)?(?:fold|×|x)\b(?:\s+\w+){{0,6}}?\s+from\s+(?P<a>{NUM})\s?%?\s+(?:to|→)\s+(?P<b>{NUM})", re.I)


def _change_checks(s: Sentence):
    t = s.text
    for ft in _FROM_TO.finditer(t):
        a_s, b_s = ft.group("a"), ft.group("b")
        a, b = _f(a_s), _f(b_s)
        # the stated difference must sit right next to the "from A to B" phrase, before it or after it
        window_after = t[ft.end(): ft.end() + 60]
        window_before = t[max(0, ft.start() - 70): ft.start()]
        if _YEAR.fullmatch(a_s.strip()) or _YEAR.fullmatch(b_s.strip()):
            continue    # "from 1989 to 2013" is a period, not a change
        m, where = next((m for m in (rx.match(window_after) for rx in _BY_AFTER) if m), None), "after"
        if m is None:
            m, where = _BY_BEFORE.search(window_before), "before"
        if m is None:
            continue
        d_s, unit = m.group("d"), (m.group("u") or "").strip().lower()
        if d_s in (a_s, b_s) and where == "before":
            continue
        d = _f(d_s)
        ha, hb, hd = _half(a_s), _half(b_s), _half(d_s)
        diff_lo, diff_hi = max(0.0, abs(b - a) - ha - hb), abs(b - a) + ha + hb
        absolute_ok = _matches_printed(d_s, diff_lo, diff_hi)
        rel = abs(b - a) / abs(a) * 100 if a else None
        rel_ok = False
        if a:
            rel_lo = diff_lo / (abs(a) + ha) * 100
            rel_hi = diff_hi / max(abs(a) - ha, 1e-12) * 100
            rel_ok = _matches_printed(d_s, rel_lo, rel_hi)
        pct_unit = unit in ("%", "percent")
        point_unit = "point" in unit or unit in ("pp", "p.p.")
        if point_unit:
            ok, reading = absolute_ok, "absolute"
        elif pct_unit and not (ft.group("ua") or ft.group("ub")) and not _looks_percent(t, ft):
            ok, reading = absolute_ok or rel_ok, "relative or absolute"
        else:
            ok, reading = absolute_ok or rel_ok, "absolute or relative"
        dec = max(_dec(d_s), 1)
        calc = f"|{b_s} − {a_s}| = {_fmt(abs(b - a), dec)}"
        if rel is not None:
            calc += f"; relative change {_fmt(abs(b - a), dec)} / {a_s.strip()} × 100 = {_fmt(rel, dec)}%"
        stated = f"{d_s}{' ' + unit if unit and unit != '%' else unit}"
        yield dict(kind="stated_change", ok=ok, m=ft, stated=stated, computed=calc.split(";")[0].split("= ")[-1],
                   formula=calc,
                   msg=(f"The paper states a change of {stated} from {a_s} to {b_s}, but neither the absolute "
                        f"difference ({_fmt(abs(b - a), dec)}) nor the relative change "
                        f"({_fmt(rel, dec) + '%' if rel is not None else 'undefined'}) rounds to it."
                        if not ok else f"Change of {stated} from {a_s} to {b_s} checks out ({reading} reading)."),
                   severity="high", details={"from": a, "to": b, "stated_change": d, "reading": reading})
        # direction: "increased from 40 to 30" says up but the numbers go down
        verb_zone = t[max(0, ft.start() - 60): ft.start()]
        verbs = [(v.start(), "up") for v in _UP.finditer(verb_zone)] + [(v.start(), "down") for v in _DOWN.finditer(verb_zone)]
        if verbs and a != b:
            said = max(verbs)[1]
            went = "up" if b > a else "down"
            if said != went:
                yield dict(kind="change_direction", ok=False, m=ft, stated=f"{said}", computed=f"{went}",
                           formula=f"{a_s} → {b_s} is a{'n increase' if went == 'up' else ' decrease'}",
                           msg=f"The wording says the value went {said}, but {a_s} → {b_s} goes {went}.",
                           severity="medium", details={"from": a, "to": b})
    for m in _FOLD.finditer(t):
        a_s, b_s, d_s = m.group("a"), m.group("b"), m.group("d")
        a, b = _f(a_s), _f(b_s)
        if not a or not b:
            continue
        r = max(a, b) / min(a, b)
        ha, hb = _half(a_s), _half(b_s)
        lo_v, hi_v = min(a, b), max(a, b)
        r_lo = (hi_v - (hb if b >= a else ha)) / (lo_v + (ha if b >= a else hb))
        r_hi = (hi_v + (hb if b >= a else ha)) / max(lo_v - (ha if b >= a else hb), 1e-12)
        ok = _matches_printed(d_s, r_lo, r_hi) or _matches_printed(d_s, r_lo - 1, r_hi - 1)   # "3-fold more" readings
        yield dict(kind="fold_change", ok=ok, m=m, stated=f"{d_s}×", computed=f"{_fmt(r, max(_dec(d_s), 1))}×",
                   formula=f"{max(a, b):g} / {min(a, b):g} = {_fmt(r, max(_dec(d_s), 1))}",
                   msg=(f"A {d_s}-fold change is stated, but {b_s} vs {a_s} is a ratio of {_fmt(r, 2)}."
                        if not ok else f"{d_s}-fold change from {a_s} to {b_s} checks out."),
                   severity="medium", details={"from": a, "to": b})


def _looks_percent(t: str, ft: re.Match) -> bool:
    return bool(re.search(r"%|percent|accuracy|rate", t[max(0, ft.start() - 40): ft.end() + 10], re.I))


# ---- 3. an estimate must lie inside its own confidence interval -----------------------------------------------------
_CI = re.compile(
    rf"(?P<est>{SNUM})\s*(?:%\s*)?[(\[,;]\s*(?:95|90|99)\s?%\s*(?:CI|C\.I\.|confidence interval|CrI|credible interval)"
    rf"\s*[:=,]?\s*(?:of\s+)?[(\[]?\s*(?P<lo>{SNUM})\s*%?\s*(?:to|,|;|[-−–—])\s*(?P<hi>{SNUM})", re.I)


def _ci_checks(s: Sentence):
    for m in _CI.finditer(s.text):
        est_s, lo_s, hi_s = m.group("est"), m.group("lo"), m.group("hi")
        est, lo, hi = _f(est_s), _f(lo_s), _f(hi_s)
        if lo > hi:
            lo, hi, lo_s, hi_s = hi, lo, hi_s, lo_s
        tol = max(_half(est_s), _half(lo_s), _half(hi_s))
        ok = lo - tol <= est <= hi + tol
        if lo == hi:
            continue
        yield dict(kind="ci_contains_estimate", ok=ok, m=m, stated=f"{est_s.strip()} [{lo_s.strip()}, {hi_s.strip()}]",
                   computed="inside" if ok else "outside", formula=f"{lo_s.strip()} ≤ {est_s.strip()} ≤ {hi_s.strip()}",
                   msg=(f"The point estimate {est_s.strip()} lies outside its own confidence interval "
                        f"[{lo_s.strip()}, {hi_s.strip()}]." if not ok
                        else f"Estimate {est_s.strip()} lies inside its interval [{lo_s.strip()}, {hi_s.strip()}]."),
                   severity="high", details={"estimate": est, "lower": lo, "upper": hi})


# ---- 4. p-values recomputed from the test statistic (the statcheck idea) ------------------------------------------
_P = r"[,;]\s*p\s*(?P<op>[<>=≤≥])\s*(?P<p>0?\.\d+|1(?:\.0+)?)"
_TESTS = [
    ("t", re.compile(rf"\bt\s*\(\s*(?P<df1>{NUM})\s*\)\s*=\s*(?P<v>{SNUM})\s*{_P}", re.I)),
    ("F", re.compile(rf"\bF\s*\(\s*(?P<df1>\d+)\s*,\s*(?P<df2>{NUM})\s*\)\s*=\s*(?P<v>{NUM})\s*{_P}")),
    ("chi2", re.compile(rf"(?:χ|chi)\s*2?\s*(?:²|\^2)?\s*\(\s*(?P<df1>\d+)(?:\s*,\s*N\s*=\s*\d+)?\s*\)\s*=\s*(?P<v>{NUM})\s*{_P}", re.I)),
    ("r", re.compile(rf"\br\s*\(\s*(?P<df1>\d+)\s*\)\s*=\s*(?P<v>{SNUM})\s*{_P}")),
    ("z", re.compile(rf"\b[zZ]\s*=\s*(?P<v>{SNUM})\s*{_P}")),
]


def _p_of(test: str, v: float, df1: float | None, df2: float | None) -> float:
    from scipy import stats
    v = abs(v)
    if test == "t":
        return 2 * stats.t.sf(v, df1)
    if test == "F":
        return stats.f.sf(v, df1, df2)
    if test == "chi2":
        return stats.chi2.sf(v, df1)
    if test == "z":
        return 2 * stats.norm.sf(v)
    if test == "r":
        if v >= 1:
            return 0.0
        tv = v * (df1 / (1 - v * v)) ** 0.5
        return 2 * stats.t.sf(tv, df1)
    raise ValueError(test)


def _p_checks(s: Sentence):
    try:
        import scipy  # noqa: F401
    except ImportError:   # pragma: no cover - scikit-learn depends on SciPy, so it is normally present
        return
    for test, rx in _TESTS:
        for m in rx.finditer(s.text):
            v_s = m.group("v")
            df1 = _f(m.group("df1")) if "df1" in rx.groupindex and m.group("df1") else None
            df2 = _f(m.group("df2")) if "df2" in rx.groupindex and m.group("df2") else None
            op, p_s = m.group("op"), m.group("p")
            p = _f(p_s)
            h = _half(v_s)
            vals = [abs(_f(v_s)) - h, abs(_f(v_s)) + h]
            pa, pb = (_p_of(test, max(x, 0.0), df1, df2) for x in vals)
            pmin, pmax = min(pa, pb), max(pa, pb)
            pc = _p_of(test, _f(v_s), df1, df2)
            if op in "=":
                ok = _matches_printed(p_s, pmin, pmax)
            elif op in "<≤":
                ok = pmin < p + 1e-12
            else:
                ok = pmax > p - 1e-12
            decision_flip = (not ok) and ((p <= 0.05) != (pc <= 0.05)) and op in "=<≤"
            dfs = f"({m.group('df1')}{', ' + m.group('df2') if df2 is not None else ''})" if df1 is not None else ""
            yield dict(kind="p_value", ok=ok, m=m, stated=f"p {op} {p_s}", computed=f"p = {pc:.4f}",
                       formula=f"two-tailed p for {test}{dfs} = {v_s.strip()} is {pc:.4f}"
                               + (" (one-tailed for F and χ²)" if test in ("F", "chi2") else ""),
                       msg=(f"Recomputed p = {pc:.4f} from {test}{dfs} = {v_s.strip()}, which does not agree with the "
                            f"reported p {op} {p_s}" + (" and changes the conclusion at α = .05." if decision_flip else ".")
                            if not ok else f"p {op} {p_s} agrees with {test}{dfs} = {v_s.strip()} (p = {pc:.4f})."),
                       severity="high" if decision_flip else "medium", details={"test": test, "statistic": _f(v_s),
                                                                               "df1": df1, "df2": df2, "p_computed": pc})


# ---- 5. tables: totals, averages and F1 recomputed from the other cells of the same row or column -----------------
_CELL_NUM = re.compile(r"^\s*(?P<v>[-−–]?\d{1,3}(?:,\d{3})+|[-−–]?\d+(?:\.\d+)?)\s*%?\s*(?:\(\s*[\d.]+\s*\)|±\s*[\d.]+)?\s*[*†‡]*$")
_TOTAL_HEAD = re.compile(r"^(?:total|all|sum|overall|n\s*total)\.?$", re.I)
_AVG_HEAD = re.compile(r"^(?:avg\.?|average|mean|macro[- ]?avg\.?|avg\s*score|average\s*score|score\s*avg\.?)$", re.I)
_SKIP_HEAD = re.compile(r"param|size|#|count|^n$|year|time|speed|flops|layer|dim|batch|step|epoch|token|cost|latency|"
                        r"memory|rank|^k$|^d$|^h$|^l$", re.I)
_P_HEAD = re.compile(r"^(?:p|prec\.?|precision)$", re.I)
_R_HEAD = re.compile(r"^(?:r|rec\.?|recall)$", re.I)
_F_HEAD = re.compile(r"^(?:f1|f|f-1|f1[- ]score|f[- ]score|f-measure)$", re.I)


def parse_row(text: str):
    """'Table row: BERT; MNLI: 84.6/83.4; Average: 79.6' -> ('BERT', [('MNLI', '84.6/83.4'), ('Average', '79.6')])."""
    if not text.startswith("Table row: "):
        return None
    parts = [p.strip() for p in text[len("Table row: "):].split("; ")]
    label, cells = "", []
    for i, p in enumerate(parts):
        m = re.match(r"^([^:]{1,40}):\s(.*)$", p)
        if m:
            cells.append((m.group(1).strip(), m.group(2).strip()))
        elif i == 0:
            label = p
        else:
            cells.append(("", p))
    return label, cells


def _cell_values(raw: str) -> list[str] | None:
    """Printed numbers in a cell ('84.6/83.4' holds two); None when the cell is not purely numeric."""
    out = []
    for piece in raw.split("/"):
        m = _CELL_NUM.match(piece)
        if not m:
            return None
        out.append(m.group("v").replace(",", ""))
    return out


def _row_checks(s: Sentence, macro_doc: bool):
    parsed = parse_row(s.text)
    if not parsed:
        return
    label, cells = parsed
    vals = [(h, _cell_values(c)) for h, c in cells]
    whole = re.match(r".*", s.text)
    # totals: the cell under "Total"/"All" equals the sum of the other integer cells of the row
    for i, (h, v) in enumerate(vals):
        if not h or not v or len(v) != 1:
            continue
        others = [(hh, vv) for j, (hh, vv) in enumerate(vals) if j != i and vv and hh and not _SKIP_HEAD.search(hh)]
        nums = [x for _, vv in others for x in vv]
        if _TOTAL_HEAD.match(h) and len(nums) >= 2 and all("." not in x for x in nums + v) \
                and sum(1 for hh, _ in vals if hh and _TOTAL_HEAD.match(hh)) == 1 \
                and len(others) == sum(1 for hh, vv in vals if hh and hh != h):
            total, comp = int(v[0]), sum(int(_f(x)) for x in nums)
            ok = total == comp
            if not ok and len(nums) >= 3 and total == comp - int(_f(nums[0])):
                nums, comp, ok = nums[1:], comp - int(_f(nums[0])), True   # the first cell was a category code
            yield dict(kind="table_row_total", ok=ok, m=whole, stated=v[0], computed=str(comp),
                       formula=" + ".join(nums) + f" = {comp}",
                       msg=(f"Row '{label}': the '{h}' cell is {v[0]}, but the other cells add up to {comp}."
                            if not ok else f"Row '{label}': '{h}' {v[0]} equals the sum of the other cells."),
                       severity="medium", details={"row": label, "column": h})
        elif _AVG_HEAD.match(h) and len(nums) >= 2:
            before = [x for j, (hh, vv) in enumerate(vals) if j < i and vv and hh and not _SKIP_HEAD.search(hh) for x in vv]
            ok, used = False, nums
            for cand in ([nums, before] if before and before != nums else [nums]):
                if len(cand) < 2:
                    continue
                mean = sum(_f(x) for x in cand) / len(cand)
                hmax = max(_half(x) for x in cand)
                if _matches_printed(v[0], mean - hmax, mean + hmax):
                    ok, used = True, cand
                    break
            mean = sum(_f(x) for x in used) / len(used)
            yield dict(kind="table_row_average", ok=ok, m=whole, stated=v[0], computed=_fmt(mean, _dec(v[0])),
                       formula=f"({' + '.join(used)}) / {len(used)} = {_fmt(mean, _dec(v[0]))}",
                       msg=(f"Row '{label}': the plain mean of the row's cells is {_fmt(mean, _dec(v[0]))}, not the printed "
                            f"'{h}' {v[0]}. Averages are sometimes weighted or skip columns, so check the caption."
                            if not ok else f"Row '{label}': '{h}' {v[0]} is the mean of the row's cells."),
                       severity="low", details={"row": label, "column": h}, not_reproduced=not ok)
    # F1 must be the harmonic mean of the precision and recall printed beside it
    p = r = None
    for h, v in vals:
        if not h or not v or len(v) != 1:
            continue
        if _P_HEAD.match(h):
            p = v[0]
        elif _R_HEAD.match(h):
            r = v[0]
        elif _F_HEAD.match(h) and p is not None and r is not None:
            P, R, hp, hr = _f(p), _f(r), _half(p), _half(r)
            f1 = lambda a, b: 2 * a * b / (a + b) if a + b else 0.0
            comp = f1(P, R)
            ok = _matches_printed(v[0], f1(max(P - hp, 0), max(R - hr, 0)), f1(P + hp, R + hr))
            small = abs(comp - _f(v[0])) <= (1.0 if max(P, R) > 1 else 0.01)
            yield dict(kind="f1_harmonic_mean", ok=ok, m=whole, stated=v[0], computed=_fmt(comp, _dec(v[0])),
                       formula=f"2 × {p} × {r} / ({p} + {r}) = {_fmt(comp, _dec(v[0]))}",
                       msg=(f"Row '{label}': F1 {v[0]} is not the harmonic mean of P {p} and R {r} "
                            f"({_fmt(comp, _dec(v[0]))})." + (" When F1 is averaged over runs or classes it can differ "
                                                             "slightly from the harmonic mean of the averaged P and R."
                                                             if small or macro_doc else "")
                            if not ok else f"Row '{label}': F1 {v[0]} = harmonic mean of P {p} and R {r}."),
                       severity="medium", details={"row": label}, not_reproduced=(not ok and (small or macro_doc)))
            p = r = None


_NON_ADDITIVE = re.compile(r"avg|average|mean|median|rate|ratio|%|percent|per|score|sd|std|±", re.I)


def _subtotals(col: list[tuple[str, int]]):
    """Read a column as groups of rows each closed by a subtotal row (a row within 2% of the rows above it).

    Returns (subtotal rows as (index, printed, recomputed), sum of subtotals plus the rows after the last one)."""
    subs, run, parts, top = [], 0, 0, 0
    for i, (_, v) in enumerate(col):
        if parts >= 2 and run and abs(v - run) <= 0.02 * run:
            subs.append((i, v, run))
            top += v
            run, parts = 0, 0
        else:
            run += v
            parts += 1
    return subs, top + run


def _column_total_checks(doc: Document):
    """A 'Total'/'All' row must equal the column sums of the rows above it in the same table.

    When the plain sum fails, the column is re-read as groups closed by subtotal rows ("North region" under its
    states); if the total then matches the subtotals, each subtotal is checked against its own group instead."""
    group: list[tuple[Sentence, str, list]] = []

    def flush():
        if len(group) < 3:
            return
        for k, (s, label, cells) in enumerate(group):
            if not _TOTAL_HEAD.match(label or ""):
                continue
            others = [g for j, g in enumerate(group) if j != k]
            for h, raw in cells:
                v = _cell_values(raw)
                if not h or not v or len(v) != 1 or "." in v[0] or _NON_ADDITIVE.search(h):
                    continue
                col = []
                for _, olabel, oc in others:
                    hv = [_cell_values(c) for hh, c in oc if hh == h]
                    if len(hv) != 1 or not hv[0] or len(hv[0]) != 1 or "." in hv[0][0]:
                        col = None
                        break
                    col.append((olabel, int(_f(hv[0][0]))))
                if not col or len(col) < 2:
                    continue
                total = int(_f(v[0]))
                comp = sum(x for _, x in col)
                m = re.match(r".*", s.text)
                if comp == total:
                    yield s, dict(kind="table_column_total", ok=True, m=m, stated=v[0], computed=str(comp),
                                  formula=" + ".join(str(x) for _, x in col) + f" = {comp}",
                                  msg=f"Column '{h}': '{label}' {v[0]} equals the sum of the rows.",
                                  severity="medium", details={"row": label, "column": h})
                    continue
                subs, sub_total = _subtotals(col)
                if subs and sub_total == total:
                    yield s, dict(kind="table_column_total", ok=True, m=m, stated=v[0], computed=str(sub_total),
                                  formula=" + ".join(str(p) for _, p, _ in subs)
                                  + (" + rows after the last subtotal" if sub_total != sum(p for _, p, _ in subs) else "")
                                  + f" = {sub_total}",
                                  msg=f"Column '{h}': '{label}' {v[0]} equals the sum of the {len(subs)} subtotal rows.",
                                  severity="medium", details={"row": label, "column": h, "subtotals": len(subs)})
                    start = 0
                    for i, printed, rec in subs:
                        srow = others[i]
                        members = [x for _, x in col[start:i]]
                        start = i + 1
                        ok = printed == rec
                        yield srow[0], dict(
                            kind="table_column_total", ok=ok, m=re.match(r".*", srow[0].text), stated=str(printed),
                            computed=str(rec), formula=" + ".join(map(str, members)) + f" = {rec}",
                            msg=(f"Column '{h}': the subtotal row '{srow[1]}' is {printed}, but the {len(members)} rows "
                                 f"above it add up to {rec} (a difference of {abs(rec - printed)})."
                                 if not ok else f"Column '{h}': subtotal '{srow[1]}' {printed} equals its rows."),
                            severity="high", details={"row": srow[1], "column": h, "subtotal": True})
                    continue
                yield s, dict(kind="table_column_total", ok=False, m=m, stated=v[0], computed=str(comp),
                              formula=" + ".join(str(x) for _, x in col) + f" = {comp}",
                              msg=f"Column '{h}': the '{label}' row is {v[0]}, but the other rows add up to {comp}.",
                              severity="medium", details={"row": label, "column": h})

    prev_key = None
    for s in doc.sentences:
        parsed = parse_row(s.text)
        if not parsed:
            continue
        label, cells = parsed
        key = (s.page, tuple(h for h, _ in cells))
        if key != prev_key:
            yield from flush()
            group = []
        group.append((s, label, cells))
        prev_key = key
    yield from flush()


_CHECKERS = (_percent_checks, _change_checks, _ci_checks, _p_checks)
KIND_LABEL = {
    "percent_of_count": "Percentage of a count", "stated_change": "Stated difference", "change_direction": "Direction of change",
    "fold_change": "Fold change", "ci_contains_estimate": "Estimate inside its interval", "p_value": "p-value vs test statistic",
    "table_row_total": "Row total", "table_column_total": "Column total", "table_row_average": "Row average",
    "f1_harmonic_mean": "F1 from precision and recall",
}


def _results(doc: Document):
    macro_doc = any(re.search(r"\bmacro", s.text, re.I) for s in doc.sentences)
    for s in doc.sentences:
        if s.text.startswith("Table row: "):
            for r in _row_checks(s, macro_doc):
                yield s, r
        if s.kind == "meta":
            continue
        for fn in _CHECKERS:
            for r in fn(s):
                yield s, r
    yield from _column_total_checks(doc)


def audit(doc: Document) -> dict:
    """Run every check on every sentence (prose and table rows) and return the report dict."""
    checks: list[Check] = []
    for s, r in _results(doc):
        status = "consistent" if r["ok"] else ("not_reproduced" if r.get("not_reproduced") else "inconsistent")
        checks.append(Check(
            id="", kind=r["kind"], status=status, severity="low" if status != "inconsistent" else r["severity"],
            message=r["msg"], page=s.page, sentence_id=s.id, section=s.section, quote=_quote(s.text, r["m"]),
            formula=r["formula"], stated=r["stated"], computed=r["computed"], details=r.get("details", {})))
    order = {"inconsistent": 0, "not_reproduced": 1, "consistent": 2}
    sev = {"high": 0, "medium": 1, "low": 2}
    checks.sort(key=lambda c: (order[c.status], sev[c.severity], c.page, c.sentence_id))
    for i, c in enumerate(checks, 1):
        c.id = f"N{i}"
    by_kind: dict[str, dict[str, int]] = {}
    for c in checks:
        k = by_kind.setdefault(c.kind, {"checked": 0, "consistent": 0, "inconsistent": 0, "not_reproduced": 0})
        k["checked"] += 1
        k[c.status] += 1
    return {
        "n_checked": len(checks),
        "n_consistent": sum(c.status == "consistent" for c in checks),
        "n_inconsistent": sum(c.status == "inconsistent" for c in checks),
        "n_not_reproduced": sum(c.status == "not_reproduced" for c in checks),
        "by_kind": by_kind, "labels": KIND_LABEL,
        "checks": [c.to_dict() for c in checks],
        "method": ("Each check finds a statement that prints a result next to the numbers it is computed from, redoes "
                   "the calculation and compares it with the printed result, allowing for the rounding of every printed "
                   "number. Consistent checks are listed too, so the reader sees what was verified, not only what failed. "
                   "'Not reproduced' marks a result that a legitimate convention (a weighted average, macro-F1) could "
                   "explain."),
        "caveat": ("An inconsistency is a reason to look closer (a typo, a different denominator, a misread table), "
                   "not proof of an error. Numbers in figures, and statements written in forms the patterns do not "
                   "cover, are not checked."),
    }
