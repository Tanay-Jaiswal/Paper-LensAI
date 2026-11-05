# Optional AI second opinion

PaperLens's evidence ledger is rule-based: it links a claim to a passage when they share wording and numbers. A passage
that supports a claim **in other words** can be missed, and the claim is then shown as "no evidence found" or "weak".
The AI second opinion lets a reader ask a language model about one such claim.

## Off by default

It does nothing unless the person running PaperLens turns it on:

```powershell
pip install -r requirements-ai.txt              # the official 'anthropic' package
$env:ANTHROPIC_API_KEY = "..."                   # your own key; each click is a paid API request
$env:PAPERLENS_AI_SECOND_OPINION = "1"
python -m paperlens serve
```

Optional: `PAPERLENS_AI_MODEL` (default `claude-opus-5-5`). When it is on, the page header says "optional AI second
opinion on", and a dashed box labelled **AI-assisted** appears under each claim in the Evidence Ledger with an
"Ask an AI second opinion" button.

## What it does

1. PaperLens takes the claim and up to 8 of the closest body sentences its own ranking found, **including ones the
   rules rejected** for having too little wording in common (that is the case this is for). Fragments, licence lines
   and equations are left out.
2. Only that text (the claim and those sentences) is sent to Anthropic, once, when the reader clicks.
3. The model answers in a fixed JSON format: supported / partly supported / not supported, the numbers of the passages
   that support the claim, and a one-paragraph reason.
4. PaperLens shows the verdict, the reason and the passages it points to. **The quotes are PaperLens's own copies of the
   paper's sentences**, never text written by the model. An answer naming a passage that was not offered, or that
   cannot be read, is discarded and shown as "not checked".

## What it never does

* It never changes the rule-based rating, the score card grade, the checklist, the evidence gaps or any report
  download. The answer is stored separately (`second_opinion.json` in the analysis folder) and shown only in its box.
* It never runs by itself: one click asks about one claim.
* It is not counted in any evaluation figure in this repository.

## Testing status

The code is tested with a fake model client (`tests/test_second_opinion.py`): request shape, the passage check,
discarded answers, refusals, a missing API key, and that the rule-based results are unchanged. **It has not been run
against the real API**, because no API key was available while it was built. Before relying on it, try it on a few
claims you can check yourself, and keep in mind that the model can be wrong in both directions.
