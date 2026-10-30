---
name: transcribe-document
description: Transcribe image. Use when given image to transcribe.
---

# Transcribe document

If the user says the document is not Rosenberg-related, do only steps 1 and 4 (transcribe, then reconcile with Transkribus) and give an English translation per step 5 in the answer. Do not search for, create, or modify any record or facts under `data/`.

## 1. Transcribe the image

Read the image. Transcribe it line by line, keeping the exact original vernacular spelling (Middle High German / Early New High German, or Latin). Expand scribal abbreviations inside brackets `[ ]`. Mark uncertain letters or words `[?]` and lost or illegible text `[…]`.

For each ambiguous letter, note the paleographical reasoning briefly: minim clusters (`n`/`u`/`m`/`i`), long `s` versus `f`, `b` versus `l`, `c` versus `t`, `u` versus `v`, nasal strokes, and similar. Give a confidence level. Do not guess to produce fluent text. Words hidden by stains or folds stay `[…]`.

Check the date against the century. 1400 and later is 15th century even if the user says 14th.

## 2. Identify the record

- Take the archive and shelfmark from the file name (for example `Generallandesarchiv Karlsruhe 43 Nr. 5296.png` is source `43 Nr. 5296`).
- Find the record under `data/documents/` with `grep -rl "<shelfmark>" data/documents`. Name the file in your answer. Check the date from the text against the file name, which is normally `YYYY-MM-DD.json`.
- If no record matches, or several do, ask the user.
- Use the existing archive regest as context for names and places, but not as proof of what the scan says.

## 3. Prepare the record

In the matched entry:
- Delete the `english` field, if present.
- Rename the existing `german` or `latin` field to `summary`. These fields hold the archive's regest, not the document text.

Leave `source`, `url`, `img` and other fields unchanged.

## 4. Ask for the Transkribus transcription

Stop and ask the user to paste the Transkribus transcription of this document. Wait for the answer.

Then reconcile your reading, the Transkribus text, the archive summary and the context into one text. State briefly:
- which readings you took from Transkribus and which from your own reading;
- which words are still uncertain, with the reasoning.

Where Transkribus produces nonsense, prefer your own reading or the standard formula (for example `ledig und los`, `Insigel laszen hencken`). Do not harmonize against the scan using only the summary. Mark names that rest only on the summary.

Store the result in `german` (or `latin`):
- Keep the original spelling, including `v`/`u`, `ss`/`sz` and doubled consonants. Do not modernize.
- Routine abbreviations are expanded silently, with no brackets, so that place and person matching works. Keep `[…]` for gaps and `[?]` for doubtful words.
- Plain text only, as one string.

If the user corrects a reading afterwards, update the field and everything derived from it.

## 5. English translation

Write `english` as a faithful translation of the stored text:
- Keep historically meaningful German or Latin terms (`Eigenleute`, `Komtur`, `Vogt zu Dürn`, `Ritter`, `Edelknecht`) and place titles after the full name, per `rules/facts.md`.
- Keep family names intact (`von Rosenberg`).
- Carry over `[…]` for gaps and mark doubtful passages `[?]`. Do not smooth over what the text does not say.
- Render dates in the usual modern form and keep saint's-day dates literal (for example "on St. Thomas's day, the holy apostle").

## 6. Improve the facts

Follow `rules/facts.md` and `rules/json-formats.md`, and the `fact-extraction-review` skill if the work is substantial.

- Verify every existing fact against the German text. Correct or delete unsupported and contradicted facts.
- Use typed facts (`parent`, `sibling`, `spouse`, `kin`, `title`) for stated relationships and titles. Use prose facts for the rest.
- Record death separately. `selig` or "deceased" gives "was deceased" (by the document date) and nothing more.
- Omit prices and amounts. State the people, property, place and parties of each transaction. One assertion per fact.
- Normalize names through `data/names.md` (for example Else to Elisabeth, Engelhart to Engelhard). The validator rejects unnormalized given names. Check places with `python3 scripts/list_place_variations.py`.
- Do not link `people.json` IDs or merge namesakes without evidence in this document. Report possible matches instead.
- Do not infer relationships or residence from proximity. Put assumptions in `guesses`, not `facts`.
- Use the source's own designation in title arrays (`selig`, not `verstorben`).

## 7. Verify and report

- `python3 -c "import json; json.load(open('<file>'))"` and `python3 scripts/validate_facts.py` must report no errors.
- Review `git diff` of the file. Confirm that only `summary`, `german`/`latin`, `english` and `facts` changed.
- Report: the file identified; the uncertain readings; each fact with its supporting quote and status (supported / partially supported / unsupported / contradicted), as in `rules/facts.md`; and open questions such as possible person matches.
