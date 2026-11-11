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

The default classifier chooses among eleven options:

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
| `unrelated` | None of the eight families is substantively represented |
| `mixed` | Multiple listed families are explicitly represented |
| `uncertain` | Evidence is insufficient to distinguish a family |

The prompt incorporates the research review's qualifications, including the
Mönch namesake warning and the unproved Brandenburg/Rosenburg connection.

A paired local check on 2026-11-11 compared the previous and research-derived
prompts on 29 documents sampled from the six requested labels. Agreement with
existing labels increased from 15/29 (51.7%) to 26/29 (89.7%); Franken improved
from 0/5 to 2/5, with three remaining abstentions. Excluding five examples used
in the research, agreement increased from 10/24 to 21/24. The separate
1387-06-22 diagnostic changed from `uncertain` to `franconian`. English was
excluded in both runs. These are small-sample label-agreement results, not a
validation of confidence or false-positive rates. The configs, probabilities,
raw responses and [comparison report](reports/kev-family-comparison-2026-11-11/comparison.md)
are saved in that ignored report directory. Existing application gates were not
revalidated by this check.

A name or place alone does not establish family relevance. The classifier uses
German/Latin/summary text, citations, titles, date, and place, excluding English
translations, existing labels, and facts. Explicit `--document` input is scored regardless of its labels or deleted
flag. The command prints the proposed choice and its probability and saves all
eleven probabilities with the raw response in `/tmp/kev-classifications.jsonl`.
Use `--output PATH` to choose another result file. It does not modify the document.

These eleven choices are the current defaults. `--config` can supply an older
set of criteria, including the saved nine-choice configuration used by the review
queue below. The older validation does not validate the new categories. Changes
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
