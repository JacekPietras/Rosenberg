# Kev on this Mac

Local decision model for classification, not a chat/text-generation model.
Inference runs on this Mac and does not use the ChatGPT allowance.

| Component | Current setup |
| --- | --- |
| Hardware | Apple M4 Pro, 48 GB RAM |
| Model | `jaredpalmer/kev-4b@v1.0` |
| Backend | MLX, Metal GPU (`mps`), bfloat16 |
| Python | Isolated Python 3.13; system Python 3.14 is not supported by this Kev version |
| Runtime | `/private/tmp/rosenberg-kev` |
| Model cache | `/private/tmp/rosenberg-kev-models` (about 9 GB of base weights) |
| API | `http://127.0.0.1:8009` |
| Upstream | <https://github.com/jaredpalmer/kev> |

## Start and stop

Run from a **normal macOS Terminal**; the Codex sandbox cannot access Metal:

```sh
/Users/jpietras/StudioProjects/Rosenberg/scripts/run_kev_local.sh
```

Leave that Terminal open. Ready means `Uvicorn running on http://127.0.0.1:8009`.
Initial imports/loading can be quiet; missing weights download automatically.
Stop with **Ctrl+C**, after any classification job finishes.

Check readiness from another Terminal:

```sh
curl -fsS http://127.0.0.1:8009/v1/models
```

The response should report `backend: mlx`, `device: mps`, and the pinned model.

## Use the API for other tasks

```sh
curl -s http://127.0.0.1:8009/v1/systemone \
  -H 'Content-Type: application/json' \
  -d '{"model":"kev-latest","state":"A charter issued at Boxberg.","questions":{"mentions_boxberg":{"type":"noul","instructions":"Does this text mention Boxberg?"}}}'
```

`answers.mentions_boxberg.noul` is a yes-probability between 0 and 1.
Kev also supports `choice` and `score` questions. Validate accuracy on examples
from each new task; a high probability alone is not proof of correctness.

## Propose a family for one document

See [KEV-families.md](KEV-families.md) for sourced research on all eight family
categories and unresolved distinctions, especially Schenk and Brandenburg/Rosenburg.
The default prompt contains a concise version of the research; the classifier
does not automatically load the reference file.

With the local server running, score a document JSON from the repository root:

```sh
python3 scripts/kev_classify_documents.py --document data/documents/1397-04-29.json
```

The default classifier chooses among nine options:

| Choice | Meaning |
| --- | --- |
| `franconian` | Franconian/Odenwald von Rosenberg family |
| `schenk` | Working Schenk category; research identifies Schenk von Roßberg and context-dependent Rosenberg renderings |
| `monch` | Separate Mönch/Münch von Rosenberg family |
| `rorschach` | Swiss Rorschach/Rosenberg family |
| `czech` | South Bohemian Rožmberk dynasty |
| `lengenfelder` | Family associated with Rosenberg castle near Sulzbach; Lengenfelder, Lengenfelderin, Lengenfeld, and Lengenvelder name variants |
| `orsini` | Austrian Orsini/Ursini-Rosenberg house |
| `brandenburg` | Northern Rosenberg records in Brandenburg/Magdeburg, including the Bredow association; their proposed link to Saale Rosenburg remains unproved |
| `other` | All non-target material: places, castles, addresses, residents, modern surname bearers, and other noble houses |

The prompt incorporates the research review's qualifications, including the
Mönch namesake warning and the unproved Brandenburg/Rosenburg connection.

A paired check on 2026-11-11 compared the previous eleven-choice prompt with
these nine defaults. On 45 fresh cases, label agreement improved from 29/45 to
43/45: Franken from 8/20 to 19/20, the other four tested families remained at
20/20, and non-target controls improved from 1/5 to 4/5. Including the earlier
29-case regression set gives 55/74 versus 71/74. These small samples measure
agreement with provisional labels; one existing Franken label has contrary
historical evidence. Orsini and Brandenburg were not tested. See the
[paired report and remaining errors](reports/kev-place-choice-2026-11-11/comparison.md).
The detailed Bauer research is preserved in the reference, but long Franconian
summaries were rejected because they caused false Franconian predictions.

There is no `mixed` or `uncertain` answer. If several target families occur,
the prompt selects the one most directly represented. The scores are relative
across these choices, not calibrated chances of historical correctness or
independent probabilities that each family is present. Removing abstention
categories does not resolve ambiguous evidence. `von`, `de`, and `zu` alone
do not distinguish noble family membership from origin or residence.

A name or place alone does not establish family relevance. The classifier uses
German/Latin/summary text, citations, titles, date, and place, excluding English
translations, existing labels, and facts. Explicit `--document` input is scored regardless of its labels or deleted
flag. The command prints the proposed choice and its probability and saves all
nine probabilities in the `probabilities` field, alongside the raw response in `/tmp/kev-classifications.jsonl`.
Use `--output PATH` to choose another result file. It does not modify the document.
The `.summary.json` sidecar reports `scored` successful predictions and `evaluated`
cases with a usable expected class; a single unlabelled input has `evaluated: 0`.

These nine choices are the current defaults. `--config` can supply an older
set of criteria, including the earlier configuration used by the review
queue below (which has different categories despite also having nine choices). The older validation does not validate the new categories. Changes
to the classifier also invalidate the queue's saved runner hash; refresh validation
before applying labels with that workflow.

## Rosenberg document workflow

In a second Terminal:

```sh
cd /Users/jpietras/StudioProjects/Rosenberg

# Score/check only; does not change document labels.
python3 scripts/kev_process_review_queue.py

# Score and apply labels allowed by the saved validation gate.
python3 scripts/kev_process_review_queue.py --apply
```

Run only one queue job at a time. Rerunning resumes matching cached predictions.
Writes require the frozen prompt/model/source checks to match; changed inputs
are rescored or skipped. Uncertain records stay in review. This workflow makes
no deletions and changes only labels, preserving facts and source text.

Local artifacts are in `reports/kev-improvement/`:

- `backlog-status.json`: current stage and final counts.
- `backlog-progress.log`: per-document scoring progress.
- `backlog-applied.jsonl`: audit receipts for applied/skipped changes.
- `frozen-config.json`, `guard-selection.json`, `application-validation.json`:
  the validated configuration and acceptance rules; do not bypass failed checks.

These reports are **ignored by Git**. Back them up if you want to preserve the
validated setup and cache. Changing the model or task requires fresh validation.

## Restore the runtime if temporary files disappear

`/private/tmp` can be cleared by macOS. With `uv` installed, restore the same
runtime revision from a normal Terminal:

```sh
test -d /private/tmp/rosenberg-kev/.git || \
  git clone --filter=blob:none --sparse https://github.com/jaredpalmer/kev.git /private/tmp/rosenberg-kev
git -C /private/tmp/rosenberg-kev checkout 2074cc44256200bb37540103fa4572901faa10f3
git -C /private/tmp/rosenberg-kev sparse-checkout set kev
cd /private/tmp/rosenberg-kev
UV_CACHE_DIR=/private/tmp/rosenberg-kev-cache \
UV_PYTHON_INSTALL_DIR=/private/tmp/rosenberg-kev-python \
  uv sync --extra serve --no-dev --python 3.13 --frozen
```

Then start the launcher again. If the model cache was cleared, it must download
the weights again. `KEV_RUNTIME_DIR` and `HF_HOME` can override the launcher's
runtime/cache paths. Do not use `pip install kev`: that name is another project.
