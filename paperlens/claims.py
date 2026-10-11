"""Claim extraction and evidence linking (the Research Evidence Ledger core).

Claim detection is cue-based and scored, not learned: a sentence in a
claim-bearing section (abstract / introduction / results / conclusion) earns
points for assertive-contribution verbs, quantitative results, comparisons and
superlatives. Evidence linking retrieves passages from the *body* of the paper
(experiments/results/method/tables) with BM25, then boosts passages that share
the claim's exact numbers. Every link carries its page, quote and scores so a
reader can verify it. Support levels are lexical/numeric agreement, not
entailment: "strong" means the cited numbers literally appear in a results
passage, not that a model judged the claim logically proven.
"""
from __future__ import annotations

import re

from .models import Claim, Document, EvidenceLink, Sentence
from .textutils import BM25, jaccard, match_quantities, numbers_in, quantities_in, tokenize

# Headline claims live in these sections. Sentences inside results/experiments are
# treated as evidence, not as claims to be audited.
CLAIM_SECTIONS = {"abstract": 1.25, "introduction": 0.7, "conclusion": 0.75, "discussion": 0.5}
# "other" = body sections with paper-specific names ("ImageNet Classification", "II. OBSERVATION"): real papers
# often report results there, so they are eligible with a low prior.
EVIDENCE_SECTIONS = {"results": 1.0, "experiments": 0.8, "discussion": 0.5, "method": 0.35,
                     "limitations": 0.3, "appendix": 0.5, "other": 0.3}

ASSERT_RE = re.compile(
    r"\b(we (?:propose|introduce|present|develop|show|demonstrate|find|observe|prove|establish|report|achieve|obtain|"
    r"design|build|release|contribute)|achiev\w+|outperform\w*|surpass\w*|improv\w+|reduc\w+|"
    r"increas\w+|boost\w*|yield\w*|reach\w*|attain\w*|obtain\w*|beat\w*|exceed\w*|demonstrat\w+|"
    r"show\w* that|results (?:show|indicate|suggest)|our (?:model|method|approach|system|framework)\b|"
    r"state[- ]of[- ]the[- ]art|sota|novel|first to|new (?:state|record)|significant\w*|robust\w*|"
    r"generaliz\w+|faster|better|superior|higher|lower)\b", re.I)
RESULT_RE = re.compile(r"\b\d+(?:\.\d+)?\s?(?:%|percent|points?|pp|x|×|bleu|f1|auc|map|rouge|accuracy)", re.I)
COMPARE_RE = re.compile(r"\b(outperform\w*|surpass\w*|better than|superior|exceed\w*|beat\w*|compared (?:with|to)|"
                        r"over (?:the )?baseline|improv\w+ (?:over|upon|on)|from \d|than)\b", re.I)
SUPER_RE = re.compile(r"\b(state[- ]of[- ]the[- ]art|sota|best|new record|unprecedented|first to|outperforms? all)\b", re.I)
GENERAL_RE = re.compile(r"\b(generaliz\w+|robust\w*|wide range|broad(?:ly)?|across (?:all|many|diverse|various)|"
                        r"universally|any (?:domain|task)|in all settings)\b", re.I)
CONTRIB_RE = re.compile(r"\b(we (?:propose|introduce|present|develop|design|release|contribute|build)|"
                        r"our (?:main )?contributions?|novel|new (?:method|model|approach|framework|dataset))\b", re.I)
HEDGE_RE = re.compile(r"\b(may|might|could|can potentially|suggests?|appears?|seems?|likely|possibly|"
                      r"perhaps|tends? to|in some cases)\b", re.I)
NEG_RE = re.compile(r"\b(limitation|however|future work|we leave|not (?:evaluated|tested|studied)|"
                    r"beyond the scope|remains? (?:unclear|open))\b", re.I)
BACKGROUND_RE = re.compile(r"\b(prior work|previous(?:ly)?|existing (?:methods|approaches)|has been (?:proposed|studied)|"
                           r"have been proposed|is a (?:central|key|fundamental)|et al\.)", re.I)


def _is_number_row(t: str) -> bool:
    """A run of table cells that reached the prose stream ("Oracle 100.0 80.5 89.2 ...") is not a sentence."""
    toks = t.split()
    numeric = sum(1 for w in toks if re.fullmatch(r"[\d.,%±+\-−()/]+", w))
    words = sum(1 for w in toks if len(re.findall(r"[A-Za-z]", w)) >= 2)
    return words < 5 or words / len(toks) < 0.5 or numeric / len(toks) >= 0.4


def _claim_score(s: Sentence) -> tuple[float, str, bool]:
    t = s.text
    if s.kind != "text" or len(t) < 30 or len(t) > 420 or t.endswith("?"):
        return 0.0, "other", False
    if _is_number_row(t):
        return 0.0, "other", False
    if s.section not in CLAIM_SECTIONS:
        return 0.0, "other", False
    score = CLAIM_SECTIONS[s.section] * 0.4
    n_assert = len(ASSERT_RE.findall(t))
    score += min(n_assert, 3) * 0.18
    has_res = bool(RESULT_RE.search(t)) or len(numbers_in(t)) >= 1 and re.search(r"\d\.\d", t)
    if has_res:
        score += 0.30
    if COMPARE_RE.search(t):
        score += 0.15
    if SUPER_RE.search(t):
        score += 0.12
    if BACKGROUND_RE.search(t) and not re.search(r"\bwe\b|\bour\b", t, re.I):
        score -= 0.45
    if NEG_RE.search(t) and not has_res:
        score -= 0.3
    if s.section == "experiments" and not has_res:
        score -= 0.4
    if s.section == "introduction" and not (CONTRIB_RE.search(t) or has_res):
        score -= 0.25
    if s.section == "results" and not has_res and not COMPARE_RE.search(t):
        score -= 0.2
    hedged = bool(HEDGE_RE.search(t))
    if GENERAL_RE.search(t) and not BACKGROUND_RE.search(t):
        ctype = "generalization"
    elif has_res and COMPARE_RE.search(t):
        ctype = "comparison"
    elif has_res:
        ctype = "result"
    elif CONTRIB_RE.search(t):
        ctype = "contribution"
    elif SUPER_RE.search(t):
        ctype = "comparison"
    elif n_assert:
        ctype = "assertion"
    else:
        ctype = "other"
    return max(score, 0.0), ctype, hedged


def extract_claims(doc: Document, max_claims: int = 25, min_score: float = 0.62) -> list[Claim]:
    cands = []
    for s in doc.sentences:
        sc, ctype, hedged = _claim_score(s)
        if sc >= min_score and ctype != "other":
            cands.append((sc, s, ctype, hedged))
    cands.sort(key=lambda x: -x[0])
    chosen: list[tuple] = []
    for sc, s, ctype, hedged in cands:
        toks = set(tokenize(s.text))
        if any(jaccard(toks, set(tokenize(o[1].text))) > 0.6 for o in chosen):
            continue  # near-duplicate (e.g. abstract restated in conclusion)
        chosen.append((sc, s, ctype, hedged))
        if len(chosen) >= max_claims:
            break
    chosen.sort(key=lambda x: x[1].id)
    claims = []
    for i, (sc, s, ctype, hedged) in enumerate(chosen, 1):
        nums = [n for n in numbers_in(s.text) if not re.fullmatch(r"(19|20)\d\d", n)]
        claims.append(Claim(id=f"C{i}", sentence_id=s.id, text=s.text, page=s.page, section=s.section,
                            claim_type=ctype, hedged=hedged, numbers=nums, confidence=round(min(sc, 1.0), 2)))
    return claims

# ---- evidence linking ----------------------------------------------------------------------------------------------
# A passage is returned only if it is RELEVANT (Fix 1) and SUITABLE (Fix 3). Numbers count only when the quantity
# matches, not the bare literal (Fix 2). All thresholds are here, in one place, and are reported with every ledger.

MIN_LEXICAL = 0.35                 # normalised BM25 a passage needs when it shares no quantity with the claim
#                                    (chosen from the precision/coverage curves in docs/EVALUATION.md section 6)
MIN_LEXICAL_WITH_QUANTITY = 0.12   # ... when it does share at least one matched quantity
MIN_CONTENT_TOKENS = 6             # shorter passages are headings or fragments
MAX_NON_PROSE = 0.5                # share of tokens without a 3-letter run above which text is symbols/numbers
CAPTION_MIN_LEXICAL = 0.45         # a caption with no matched quantity must clear this to count as a stated result
CAPTION_MIN_TOKENS = 12
RESTATEMENT_JACCARD = 0.6          # near-copy of the claim ...
RESTATEMENT_CONTAINMENT = 0.8      # ... or the claim's words almost all reappear
CANDIDATES_SCANNED = 30            # how far down the ranking to look for a passage that passes both tests

THRESHOLDS = {"min_lexical": MIN_LEXICAL, "min_lexical_with_quantity": MIN_LEXICAL_WITH_QUANTITY,
              "min_content_tokens": MIN_CONTENT_TOKENS, "max_non_prose": MAX_NON_PROSE,
              "caption_min_lexical": CAPTION_MIN_LEXICAL, "restatement_jaccard": RESTATEMENT_JACCARD,
              "restatement_containment": RESTATEMENT_CONTAINMENT}

STATUS_FOUND = "found"
STATUS_NONE = "no_supporting_evidence"      # body searched, nothing relevant and suitable
STATUS_UNSEARCHABLE = "no_searchable_text"  # nothing to search: a parsing/document problem, not a finding
STATUS_TEXT = {STATUS_FOUND: "", STATUS_NONE: "No supporting evidence found",
               STATUS_UNSEARCHABLE: "Evidence search not possible: no body text was extracted from this document"}

# Sections that restate the paper for another audience; like the abstract, they are not independent evidence.
SUMMARY_HEADINGS = {"author summary", "summary", "highlights", "significance statement", "significance",
                    "plain language summary", "key points", "lay summary"}
_STEP_RE = re.compile(r"^\(?\d*\)?\s*(?:Step|Case|Claim|Lemma|Proof|Theorem|Proposition|Corollary|Remark)\b\s*\d*\s*[:.]", re.I)
_CAPTION_PREFIX = re.compile(r"^(?:Table|Figure|Fig\.|FIG\.)\s*\d+\s*[:.]?\s*", re.I)


def _eligible_evidence(doc: Document, claim: Claim) -> list[Sentence]:
    """Body sentences that may be searched at all. Unsuitable ones are filtered later, with a reason."""
    out = []
    for s in doc.sentences:
        if s.id == claim.sentence_id or s.section not in EVIDENCE_SECTIONS:
            continue
        # a claim restated elsewhere in the claims zone is not independent evidence
        if s.section in ("abstract", "introduction", "conclusion"):
            continue
        out.append(s)
    return out


def _non_prose_share(text: str) -> float:
    toks = text.split()
    if not toks:
        return 1.0
    return sum(1 for w in toks if not re.search(r"[A-Za-z]{3}", w)) / len(toks)


def evidence_unsuitable(s: Sentence, claim_tokens: set, claim_values: set, matched: list[str], lex: float) -> str:
    """Why this passage cannot serve as evidence, or '' if it can. One reason per passage, checked in this order.

    Nothing is rejected for its section alone: captions, appendix text and discussion text all pass when they
    carry a matched quantity or state a result in their own words.
    """
    if s.kind == "meta":
        return "boilerplate"
    if _NUM_HEADING(s.heading) in SUMMARY_HEADINGS:
        return "summary_section"
    body = s.text.removeprefix("Table row:")
    toks = tokenize(body)
    if s.kind == "table":
        if not matched or len(toks) < 3:
            return "table_row_without_matching_value"
        # the row label (first cell) names what the row measures; it must be something the claim talks about
        label = set(tokenize(body.split(";")[0].split(":")[0]))
        return "" if (label & claim_tokens) else "table_row_for_another_quantity"
    if len(toks) < MIN_CONTENT_TOKENS:
        return "fragment"
    if _STEP_RE.match(s.text) and len(toks) < 2 * MIN_CONTENT_TOKENS:
        return "step_or_proof_heading"
    if _non_prose_share(body) > MAX_NON_PROSE:
        return "symbols_or_numbers"
    if s.kind == "caption" and not matched:
        if len(tokenize(_CAPTION_PREFIX.sub("", s.text))) < CAPTION_MIN_TOKENS or lex < CAPTION_MIN_LEXICAL:
            return "caption_label_only"
    if s.section not in ("results", "experiments"):
        tset = set(toks)
        containment = len(claim_tokens & tset) / (len(claim_tokens) or 1)
        new_values = {q.value for q in quantities_in(s.text)} - claim_values
        if (jaccard(claim_tokens, tset) >= RESTATEMENT_JACCARD or containment >= RESTATEMENT_CONTAINMENT) and not new_values:
            return "restates_claim"
    return ""


def _NUM_HEADING(heading: str) -> str:
    return re.sub(r"^(?:\d{1,2}(?:\.\d{1,2})*\.?|[IVX]+\.)\s+", "", (heading or "").strip()).rstrip(":.").lower()


def is_relevant(lex: float, matched: list[str], min_lexical: float | None = None,
                min_lexical_with_quantity: float | None = None) -> bool:
    """The abstention test: lexical agreement alone, or weaker lexical agreement plus a matched quantity."""
    a = MIN_LEXICAL if min_lexical is None else min_lexical
    b = MIN_LEXICAL_WITH_QUANTITY if min_lexical_with_quantity is None else min_lexical_with_quantity
    return lex >= a or (bool(matched) and lex >= b)


def _has_result_numbers(nums) -> bool:
    """True if the claim cites a figure that evidence should reproduce (decimal or >= 10)."""
    return any("." in n or float(n) >= 10 for n in nums)


def _claim_quantities(claim_text: str, claim_numbers: list[str] | None):
    qs = quantities_in(claim_text)
    if claim_numbers:      # the caller's list (years already removed) restricts which numbers count
        keep = set(claim_numbers)
        qs = [q for q in qs if q.value in keep or q.value.split("e")[0] in keep]
    return qs


def rank_passages(claim_text: str, claim_numbers: list[str], pool: list[Sentence]):
    """Score candidate evidence passages for a claim.

    Returns [(score, lexical, matched_quantities, sentence, shared_terms)] sorted best-first.
    score = 0.55*BM25(normalised) + 0.35*quantity agreement + 0.10*section prior + 0.10*term Jaccard,
    damped by 25% if the claim has numbers and the passage matches none of them.
    A number agrees only if value, unit and/or neighbouring words agree (textutils.Quantity.matches).
    """
    if not pool:
        return []
    docs = [tokenize(s.text) for s in pool]
    bm = BM25(docs)
    q = tokenize(claim_text)
    qset = set(q)
    norm = bm.self_score(q)
    cqs = _claim_quantities(claim_text, claim_numbers)
    wt = lambda v: 1.0 if "." in v or "e" in v or float(v) >= 100 else 0.4   # noqa: E731
    weights = {c.value: wt(c.value) for c in cqs}
    wsum = sum(weights.values()) or 1.0
    scored = []
    for i, s in enumerate(pool):
        lex = bm.score(q, i) / norm
        shared = match_quantities(cqs, quantities_in(s.text)) if cqs else []
        frac = (sum(weights[v] for v in shared) / wsum) if cqs else 0.0
        overlap = jaccard(qset, set(docs[i]))
        prior = EVIDENCE_SECTIONS.get(s.section, 0.3)
        if s.kind == "table":
            prior = max(prior, 0.9)
        total = 0.55 * min(lex, 1.0) + 0.35 * frac + 0.10 * prior + 0.1 * overlap
        if cqs and not shared:
            total *= 0.75
        scored.append((total, lex, shared, s, sorted(qset & set(docs[i]))))
    scored.sort(key=lambda x: -x[0])
    return scored


def select_passages(claim_text: str, claim_numbers: list[str], pool: list[Sentence], k: int = 3,
                    min_lexical: float | None = None, min_lexical_with_quantity: float | None = None):
    """The passages that would be returned for a claim, best first, plus counts of why candidates were rejected.

    An empty list means abstention: nothing in `pool` is both suitable and relevant. The two threshold arguments
    exist so that the precision/coverage trade-off can be measured (eval/abstention_curve.py); production code
    uses the module constants.
    """
    ctoks = set(tokenize(claim_text))
    cvals = {q.value for q in quantities_in(claim_text)}
    best, rejected = [], {}
    for cand in rank_passages(claim_text, claim_numbers, pool)[:CANDIDATES_SCANNED]:
        total, lex, shared, s, terms = cand
        why = evidence_unsuitable(s, ctoks, cvals, shared, lex)
        if not why and not is_relevant(lex, shared, min_lexical, min_lexical_with_quantity):
            why = "below_relevance_threshold"
        if why:
            rejected[why] = rejected.get(why, 0) + 1
            continue
        best.append(cand)
        if len(best) >= k:
            break
    return best, rejected


def link_evidence(doc: Document, claims: list[Claim], k: int = 3) -> list[Claim]:
    for claim in claims:
        claim.evidence, claim.rejected = [], {}
        pool = _eligible_evidence(doc, claim)
        if not pool:
            claim.support, claim.support_score = "none", 0.0
            claim.evidence_status, claim.evidence_note = STATUS_UNSEARCHABLE, STATUS_TEXT[STATUS_UNSEARCHABLE]
            claim.flags.append("no_body_passages")
            continue
        best, claim.rejected = select_passages(claim.text, claim.numbers, pool, k)
        if not best:
            claim.support, claim.support_score = "none", 0.0
            claim.evidence_status, claim.evidence_note = STATUS_NONE, STATUS_TEXT[STATUS_NONE]
            continue
        for total, lex, shared, s, terms in best:
            claim.evidence.append(EvidenceLink(s.id, s.page, s.section, s.text, round(total, 3),
                                               shared, terms[:8], round(lex, 3)))
        claim.evidence_status, claim.evidence_note = STATUS_FOUND, ""
        top = best[0]
        claim.support_score = round(top[0], 3)
        cnums = set(claim.numbers)
        matched = bool(top[2])
        if matched and top[0] >= 0.45:
            claim.support = "strong"       # a claimed quantity reappears, with good lexical agreement
        elif matched:
            claim.support = "moderate"
        elif top[0] >= 0.45 and not _has_result_numbers(cnums):
            claim.support = "moderate"     # non-numeric claim with good lexical agreement
        else:
            claim.support = "weak"         # relevant by wording only; for a numeric claim its figures were not found
    return claims


def build_ledger(doc: Document, max_claims: int = 25) -> list[Claim]:
    return link_evidence(doc, extract_claims(doc, max_claims=max_claims))
