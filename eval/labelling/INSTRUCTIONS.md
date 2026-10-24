# Checking PaperLens by hand: instructions for labellers

PaperLens reads research papers and makes decisions such as "this paper gives a link to its code" or "this passage
supports this claim". Until now those decisions have only been checked by an AI. Your answers will be the first
check by people. Thank you.

## What you need

* The file `labeller.html` you were sent. Open it in any web browser (double-click it). It works offline.
* The papers. The page lists them with a link to each one on arXiv (open "The papers" at the top).
* About 2 to 3 hours for the full set of 100 questions. You can stop and continue later in the same browser.

## How to answer

1. Type your name or initials at the top.
2. For each question, open the paper it names and look for the answer. Use the PDF's search (Ctrl+F) freely.
3. Choose the option that fits. If you found it on a specific page, type the page number.
4. Click **Save and next**. Answers are saved in your browser as you go.
5. When you are done, click **Download my answers (CSV)** and send that file back.

There are three kinds of question:

| Kind | What it asks | How to decide |
|---|---|---|
| Checklist | Does the paper report something (a code link, the hardware, model size ...)? | **yes** if the paper clearly states it for its own work; **partly** if it is mentioned but incomplete or vague (for example "trained on a GPU" without saying which); **no** if you cannot find it; **not applicable** if it makes no sense for this paper (for example model size for a paper that trains no model). |
| Evidence | Does this passage support this claim? | **yes** if the passage reports the result, number or finding the claim states, even in other words; **partly** if it supports only part of the claim; **no** if it is about something else, only restates the claim, or describes other people's work. |
| Search | Is there anything in the paper's results that supports this claim? | Look through the results, tables and figures. If you find support, choose "yes" and give the page. |

## Please

* Judge from the paper only, not from what you know about the topic.
* Do not ask PaperLens, ChatGPT, Claude or any other AI tool for help with the answers. The point is a human check.
* Do not look at PaperLens's own answers or compare notes with other labellers until you have sent your file.
* "can't tell" is a fine answer when the paper is unclear or you are unsure. Please do not guess.
* Use the note box for anything odd ("the code link is dead", "table 3 has it but only for one model").

Your name is used only to compare two people's answers on the same questions; it is not published unless you agree.

---

## For the organiser (not for labellers)

```powershell
python -m eval.labelling.make_sheet                 # builds eval/labelling/cse_check2/ (already built: 100 questions)
python -m eval.labelling.score eval/labelling/cse_check2 labels-ann.csv labels-bob.csv
```

* Send labellers `labeller.html` (or `sheet.csv` for spreadsheet users) and these instructions, nothing else. `key.json`
  holds PaperLens's answers: keep it away from labellers until they are done.
* Aim for **two labellers per question**, so agreement between people can be measured; disagreements can then be
  settled by a third person. The scorer uses the majority answer and leaves out questions without one.
* The default set is the 8 papers of the second CSE check (`data/cse_check2_papers`), where the CS checklist got 55 of
  80 decisions right against AI-assisted labels (69%). The 80 checklist questions are exactly those 80 decisions, so
  human labels will show whether that figure holds.
* Report the scorer's output as **human-labelled, n labellers**. Until labels come back, every accuracy figure in this
  project remains AI-assisted.
