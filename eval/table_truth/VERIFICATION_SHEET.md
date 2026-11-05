# Table transcriptions to verify (development papers)

These rows were transcribed by an AI assistant from images of the PDF pages. They are **not human-verified**.
To verify: open the PDF in `data/Papers/`, go to the page, compare every cell, and write `ok` or the correction in the
last column. Rules: `eval/table_truth/PROTOCOL.md`. Cells are given in the form the PDF's text layer has them; where the
printed page differs (superscripts, subscripts, symbols) the printed reading is given in the notes.

## T01: Table 2, page 7, `acl_N19-1423_bert-pre-training-of-deep-bidirectional.pdf`

SQuAD 1.1 results. Tags: numeric, two-level header, group labels, horizontal rules only, another table directly below.

- header row 1: System | Dev [spans 2] | Test [spans 2]
- header row 2: (empty) | EM | F1 | EM | F1

| # | group | cells, left to right | notes | verified? (ok / correction) |
|---|---|---|---|---|
| 1 | Top Leaderboard Systems (Dec 10th, 2018) | Human ¦ - ¦ - ¦ 82.3 ¦ 91.2 |  | |
| 2 | Top Leaderboard Systems (Dec 10th, 2018) | #1 Ensemble - nlnet ¦ - ¦ - ¦ 86.0 ¦ 91.7 |  | |
| 3 | Top Leaderboard Systems (Dec 10th, 2018) | #2 Ensemble - QANet ¦ - ¦ - ¦ 84.5 ¦ 90.5 |  | |
| 4 | Published | BiDAF+ELMo (Single) ¦ - ¦ 85.6 ¦ - ¦ 85.8 |  | |
| 5 | Published | R.M. Reader (Ensemble) ¦ 81.2 ¦ 87.9 ¦ 82.3 ¦ 88.5 |  | |
| 6 | Ours | BERTBASE (Single) ¦ 80.8 ¦ 88.5 ¦ - ¦ - | printed: BERT_BASE (Single), BASE set as a small-capital subscript | |
| 7 | Ours | BERTLARGE (Single) ¦ 84.1 ¦ 90.9 ¦ - ¦ - |  | |
| 8 | Ours | BERTLARGE (Ensemble) ¦ 85.8 ¦ 91.8 ¦ - ¦ - |  | |
| 9 | Ours | BERTLARGE (Sgl.+TriviaQA) ¦ 84.2 ¦ 91.1 ¦ 85.1 ¦ 91.8 |  | |
| 10 | Ours | BERTLARGE (Ens.+TriviaQA) ¦ 86.2 ¦ 92.2 ¦ 87.4 ¦ 93.2 |  | |

## T02: Table 5, page 8, `acl_N19-1423_bert-pre-training-of-deep-bidirectional.pdf`

Ablation over the pre-training tasks. Tags: numeric, three-level header, near prose, horizontal rules only.

- header row 1: (empty) | Dev Set [spans 5]
- header row 2: Tasks | MNLI-m | QNLI | MRPC | SST-2 | SQuAD
- header row 3: (empty) | (Acc) | (Acc) | (Acc) | (Acc) | (F1)

| # | group | cells, left to right | notes | verified? (ok / correction) |
|---|---|---|---|---|
| 1 |  | BERTBASE ¦ 84.4 ¦ 88.4 ¦ 86.7 ¦ 92.7 ¦ 88.5 |  | |
| 2 |  | No NSP ¦ 83.9 ¦ 84.9 ¦ 86.5 ¦ 92.6 ¦ 87.9 |  | |
| 3 |  | LTR & No NSP ¦ 82.1 ¦ 84.3 ¦ 77.5 ¦ 92.1 ¦ 77.8 |  | |
| 4 |  | + BiLSTM ¦ 82.1 ¦ 84.1 ¦ 75.7 ¦ 91.6 ¦ 84.9 | indented under 'LTR & No NSP' | |

## T03: Table 2, page 8, `arxiv_1706.03762v7_attention-is-all-you-need.pdf`

BLEU and training cost. Tags: numeric, two-level header, empty cells, scientific notation, merged cells, partly ruled.

- header row 1: Model | BLEU [spans 2] | Training Cost (FLOPs) [spans 2]
- header row 2: (empty) | EN-DE | EN-FR | EN-DE | EN-FR

| # | group | cells, left to right | notes | verified? (ok / correction) |
|---|---|---|---|---|
| 1 |  | ByteNet [18] ¦ 23.75 ¦ (empty) ¦ (empty) ¦ (empty) |  | |
| 2 |  | Deep-Att + PosUnk [39] ¦ (empty) ¦ 39.2 ¦ (empty) ¦ 1.0 · 1020 | printed: 1.0 · 10^20 | |
| 3 |  | GNMT + RL [38] ¦ 24.6 ¦ 39.92 ¦ 2.3 · 1019 ¦ 1.4 · 1020 | printed: 2.3 · 10^19; printed: 1.4 · 10^20 | |
| 4 |  | ConvS2S [9] ¦ 25.16 ¦ 40.46 ¦ 9.6 · 1018 ¦ 1.5 · 1020 | printed: 9.6 · 10^18; printed: 1.5 · 10^20 | |
| 5 |  | MoE [32] ¦ 26.03 ¦ 40.56 ¦ 2.0 · 1019 ¦ 1.2 · 1020 | printed: 2.0 · 10^19; printed: 1.2 · 10^20 | |
| 6 |  | Deep-Att + PosUnk Ensemble [39] ¦ (empty) ¦ 40.4 ¦ (empty) ¦ 8.0 · 1020 | printed: 8.0 · 10^20 | |
| 7 |  | GNMT + RL Ensemble [38] ¦ 26.30 ¦ 41.16 ¦ 1.8 · 1020 ¦ 1.1 · 1021 | printed: 1.8 · 10^20; printed: 1.1 · 10^21 | |
| 8 |  | ConvS2S Ensemble [9] ¦ 26.36 ¦ 41.29 ¦ 7.7 · 1019 ¦ 1.2 · 1021 | printed: 7.7 · 10^19; printed: 1.2 · 10^21 | |
| 9 |  | Transformer (base model) ¦ 27.3 ¦ 38.1 ¦ 3.3 · 1018 [spans 2] | printed: 3.3 · 10^18, one value centred across both cost columns | |
| 10 |  | Transformer (big) ¦ 28.4 ¦ 41.8 ¦ 2.3 · 1019 [spans 2] | printed: 2.3 · 10^19, one value centred across both cost columns | |

## T04: Table 1, page 5, `arxiv_1512.03385v1_deep-residual-learning-for-image-recognition.pdf`

Architectures for ImageNet. Tags: word table, architecture, merged cells, multi-line cells, full grid.

- header row 1: layer name | output size | 18-layer | 34-layer | 50-layer | 101-layer | 152-layer

| # | group | cells, left to right | notes | verified? (ok / correction) |
|---|---|---|---|---|
| 1 |  | conv1 ¦ 112×112 ¦ 7×7, 64, stride 2 [spans 5] |  | |
| 2 |  | conv2 x ¦ 56×56 ¦ 3×3 max pool, stride 2 [spans 5] | printed: conv2_x; AMBIGUOUS: a line spanning all five columns inside the conv2_x cell group, above the building blocks; whether it is a row of its own is a matter of reading | |
| 3 |  | conv2 x ¦ 56×56 ¦ 3×3, 64 3×3, 64 ×2 ¦ 3×3, 64 3×3, 64 ×3 ¦ 1×1, 64 3×3, 64 1×1, 256 ×3 ¦ 1×1, 64 3×3, 64 1×1, 256 ×3 ¦ 1×1, 64 3×3, 64 1×1, 256 ×3 | printed: conv2_x; each block is a bracketed stack of lines with its multiplier to the right | |
| 4 |  | conv3 x ¦ 28×28 ¦ 3×3, 128 3×3, 128 ×2 ¦ 3×3, 128 3×3, 128 ×4 ¦ 1×1, 128 3×3, 128 1×1, 512 ×4 ¦ 1×1, 128 3×3, 128 1×1, 512 ×4 ¦ 1×1, 128 3×3, 128 1×1, 512 ×8 | printed: conv3_x | |
| 5 |  | conv4 x ¦ 14×14 ¦ 3×3, 256 3×3, 256 ×2 ¦ 3×3, 256 3×3, 256 ×6 ¦ 1×1, 256 3×3, 256 1×1, 1024 ×6 ¦ 1×1, 256 3×3, 256 1×1, 1024 ×23 ¦ 1×1, 256 3×3, 256 1×1, 1024 ×36 | printed: conv4_x | |
| 6 |  | conv5 x ¦ 7×7 ¦ 3×3, 512 3×3, 512 ×2 ¦ 3×3, 512 3×3, 512 ×3 ¦ 1×1, 512 3×3, 512 1×1, 2048 ×3 ¦ 1×1, 512 3×3, 512 1×1, 2048 ×3 ¦ 1×1, 512 3×3, 512 1×1, 2048 ×3 | printed: conv5_x | |
| 7 |  | (empty) ¦ 1×1 ¦ average pool, 1000-d fc, softmax [spans 5] |  | |
| 8 |  | FLOPs [spans 2] ¦ 1.8×109 ¦ 3.6×109 ¦ 3.8×109 ¦ 7.6×109 ¦ 11.3×109 | printed: 1.8×10^9; printed: 3.6×10^9; printed: 3.8×10^9; printed: 7.6×10^9; printed: 11.3×10^9 | |

## T05: Table 2, page 5, `arxiv_1512.03385v1_deep-residual-learning-for-image-recognition.pdf`

Top-1 error on ImageNet validation. Tags: numeric, small, inside a text column, near prose and a figure, ruled.

- header row 1: (empty) | plain | ResNet

| # | group | cells, left to right | notes | verified? (ok / correction) |
|---|---|---|---|---|
| 1 |  | 18 layers ¦ 27.94 ¦ 27.88 |  | |
| 2 |  | 34 layers ¦ 28.54 ¦ 25.03 |  | |

## T06: Table 2.1, page 8, `arxiv_2005.14165v4_language-models-are-few-shot-learners.pdf`

Sizes, architectures and learning hyper-parameters. Tags: numeric, units, scientific notation, wide, horizontal rules only.

- header row 1: Model Name | nparams | nlayers | dmodel | nheads | dhead | Batch Size | Learning Rate

| # | group | cells, left to right | notes | verified? (ok / correction) |
|---|---|---|---|---|
| 1 |  | GPT-3 Small ¦ 125M ¦ 12 ¦ 768 ¦ 12 ¦ 64 ¦ 0.5M ¦ 6.0 × 10−4 | printed: 6.0 × 10^-4 | |
| 2 |  | GPT-3 Medium ¦ 350M ¦ 24 ¦ 1024 ¦ 16 ¦ 64 ¦ 0.5M ¦ 3.0 × 10−4 | printed: 3.0 × 10^-4 | |
| 3 |  | GPT-3 Large ¦ 760M ¦ 24 ¦ 1536 ¦ 16 ¦ 96 ¦ 0.5M ¦ 2.5 × 10−4 | printed: 2.5 × 10^-4 | |
| 4 |  | GPT-3 XL ¦ 1.3B ¦ 24 ¦ 2048 ¦ 24 ¦ 128 ¦ 1M ¦ 2.0 × 10−4 | printed: 2.0 × 10^-4 | |
| 5 |  | GPT-3 2.7B ¦ 2.7B ¦ 32 ¦ 2560 ¦ 32 ¦ 80 ¦ 1M ¦ 1.6 × 10−4 | printed: 1.6 × 10^-4 | |
| 6 |  | GPT-3 6.7B ¦ 6.7B ¦ 32 ¦ 4096 ¦ 32 ¦ 128 ¦ 2M ¦ 1.2 × 10−4 | printed: 1.2 × 10^-4 | |
| 7 |  | GPT-3 13B ¦ 13.0B ¦ 40 ¦ 5140 ¦ 40 ¦ 128 ¦ 2M ¦ 1.0 × 10−4 | printed: 1.0 × 10^-4 | |
| 8 |  | GPT-3 175B or “GPT-3” ¦ 175.0B ¦ 96 ¦ 12288 ¦ 96 ¦ 128 ¦ 3.2M ¦ 0.6 × 10−4 | printed: 0.6 × 10^-4 | |

## T07: Table 2, page 6, `arxiv_1207.7214v2_observation-of-a-new-particle-in.pdf`

Estimated numbers of Z+jets and tt background events. Tags: numeric, plus-minus values, group labels, multi-level header, inside a text column, horizontal rules only.

- header row 1: Background | Estimated numbers of events [spans 2]
- header row 2: (empty) | √s = 7 TeV | √s = 8 TeV

| # | group | cells, left to right | notes | verified? (ok / correction) |
|---|---|---|---|---|
| 1 | 4µ | Z+jets ¦ 0.3± 0.1 ±0.1 ¦ 0.5± 0.1 ±0.2 |  | |
| 2 | 4µ | t¯t ¦ 0.02±0.02±0.01 ¦ 0.04±0.02±0.02 | printed: t t-bar | |
| 3 | 2e2µ | Z+jets ¦ 0.2± 0.1 ±0.1 ¦ 0.4± 0.1 ±0.1 |  | |
| 4 | 2e2µ | t¯t ¦ 0.02±0.01±0.01 ¦ 0.04±0.01±0.01 | printed: t t-bar | |
| 5 | 2µ2e | Z+jets, t¯t ¦ 2.6± 0.4 ±0.4 ¦ 4.9± 0.8 ±0.7 | printed: Z+jets, t t-bar | |
| 6 | 4e | Z+jets, t¯t ¦ 3.1± 0.6 ±0.5 ¦ 3.9± 0.7 ±0.8 | printed: Z+jets, t t-bar | |

## T08a: Table 2 (a), page 5, `acl_2020.emnlp-main.609_fact-or-fiction-verifying-scientific-claims.pdf`

Distribution of claim labels. Tags: numeric, simple, two sub-tables under one caption, horizontal rules only.

- header row 1: Fold | SUPPORTS | NOINFO | REFUTES | All

| # | group | cells, left to right | notes | verified? (ok / correction) |
|---|---|---|---|---|
| 1 |  | Train ¦ 332 ¦ 304 ¦ 173 ¦ 809 |  | |
| 2 |  | Dev ¦ 124 ¦ 112 ¦ 64 ¦ 300 |  | |
| 3 |  | Test ¦ 100 ¦ 100 ¦ 100 ¦ 300 |  | |
| 4 |  | All ¦ 556 ¦ 516 ¦ 337 ¦ 1409 | totals row, separated by a rule | |

## T08b: Table 2 (b), page 5, `acl_2020.emnlp-main.609_fact-or-fiction-verifying-scientific-claims.pdf`

Evidence counts at various levels of granularity. Tags: numeric, empty header corner, dashes, two sub-tables under one caption.

- header row 1: (empty) | 0 | 1 | 2 | 3+

| # | group | cells, left to right | notes | verified? (ok / correction) |
|---|---|---|---|---|
| 1 |  | Cited abstracts per claim ¦ - ¦ 1278 ¦ 86 ¦ 45 |  | |
| 2 |  | Evidence abstracts per claim ¦ 516 ¦ 830 ¦ 37 ¦ 26 |  | |
| 3 |  | Rationales per abstract ¦ - ¦ 552 ¦ 290 ¦ 153 |  | |
| 4 |  | Sentences per rationale ¦ - ¦ 1542 ¦ 92 ¦ 11 |  | |

## T09: TABLE I, page 7, `arxiv_1602.03837v1_observation-of-gravitational-waves-from-a.pdf`

Source parameters for GW150914. Tags: label and value, asymmetric errors, no header, inside a text column, glyphs mis-mapped in the text layer.

- no header row

| # | group | cells, left to right | notes | verified? (ok / correction) |
|---|---|---|---|---|
| 1 |  | Primary black hole mass ¦ 36þ5 −4M⊙ | printed: 36 +5/-4 M_sun (the plus sign is mapped to 'þ' in the text layer; +5 is a superscript, -4 a subscript) | |
| 2 |  | Secondary black hole mass ¦ 29þ4 −4M⊙ | printed: 29 +4/-4 M_sun | |
| 3 |  | Final black hole mass ¦ 62þ4 −4M⊙ | printed: 62 +4/-4 M_sun | |
| 4 |  | Final black hole spin ¦ 0.67þ0.05 −0.07 | printed: 0.67 +0.05/-0.07 | |
| 5 |  | Luminosity distance ¦ 410þ160 −180 Mpc | printed: 410 +160/-180 Mpc (text layer order: 410þ160, Mpc, then -180 on the line below) | |
| 6 |  | Source redshift z ¦ 0.09þ0.03 −0.04 | printed: 0.09 +0.03/-0.04 | |

## T10: Table 1, page 7, `pmc_PMC4930190_comparison-of-high-intensity-interval-training.pdf`

Training data during intervention. Tags: numeric, plus-minus values, full grid, footnote mark, journal layout.

- header row 1: (empty) | HIIT (n = 13) | MVCT (n = 13) | p

| # | group | cells, left to right | notes | verified? (ok / correction) |
|---|---|---|---|---|
| 1 |  | Weekly training time (min) ¦ 66 ± 4 ¦ 148 ± 12 ¦ 0.000 |  | |
| 2 |  | Total training time (min) ¦ 332 ± 21 ¦ 740 ± 58 ¦ 0.000 |  | |
| 3 |  | Workload (w) ¦ 214 ± 37 ¦ 114 ± 17 ¦ 0.000 |  | |
| 4 |  | Intensity (%V O2peak) ¦ 80 ± 7* ¦ 71 ± 8 ¦ 0.000 | printed: Intensity (%V-dot O2peak): V with a dot above, 2peak as a subscript; the dot is a separate glyph in the text layer; printed: 80 ± 7 with a footnote asterisk | |
| 5 |  | HR (bpm) ¦ 162 ± 8 ¦ 158 ± 12 ¦ 0.009 |  | |
| 6 |  | HR/HRmax (%) ¦ 86 ± 4 ¦ 84 ± 4 ¦ 0.072 |  | |
| 7 |  | RPE ¦ 14 ± 1 ¦ 15 ± 1 ¦ 0.035 |  | |
| 8 |  | Total exercise energy expenditure (KJ) ¦ 12919 ± 2159 ¦ 26125 ± 2986 ¦ 0.000 |  | |
| 9 |  | Total exercise energy expenditure (Kcal) ¦ 3088 ± 516 ¦ 6244 ± 714 ¦ 0.000 |  | |

