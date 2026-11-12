#!/usr/bin/env python3
"""Classify documents labeled only ``to review`` and add family labels above 25%."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLASSIFIER = ROOT / "scripts/kev/kev_classify_documents.py"
DEFAULT_RESULTS = Path("/tmp/kev-classifications.jsonl")
THRESHOLD = 0.25
LABELS = {
    "czech": "Czechia",
    "franconian": "Franken",
    "lengenfelder": "Lengenfelder",
    "monch": "Mönch",
    "rorschach": "Rorschach",
    "schenk": "Schenk",
    "orsini": "Orsini",
    "bredow": "Bredow",
}


def only_to_review(label) -> bool:
    return label == "to review" or label == ["to review"]


def result_for(path: Path, results_path: Path) -> dict:
    wanted = str(path.resolve())
    matches = []
    if not results_path.exists():
        raise RuntimeError(f"classifier did not create results file: {results_path}")
    for number, line in enumerate(results_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"invalid classifier result at {results_path}:{number}: {exc}") from exc
        if row.get("case_id") == str(path) and str(Path(row.get("path", "")).resolve()) == wanted:
            matches.append(row)
    if not matches:
        raise RuntimeError(f"no classifier result found for {path}")
    row = matches[-1]
    if row.get("status") != "ok":
        raise RuntimeError(row.get("error", "classifier returned an error"))
    probs = row.get("probabilities")
    if not isinstance(probs, dict):
        raise RuntimeError("classifier result has no probability distribution")
    if any(name not in probs or not isinstance(probs[name], (int, float)) for name in LABELS):
        raise RuntimeError("classifier result is missing valid family probabilities")
    return row


def replace_label(path: Path, labels: list[str]) -> None:
    raw = path.read_text(encoding="utf-8")
    doc = json.loads(raw)
    if not only_to_review(doc.get("label")):
        raise RuntimeError("document label changed during classification; skipping write")
    value = ["to review", *labels]
    # Replace just the top-level label value to retain all other bytes and formatting.
    from kev_apply_labels import replace_top_level_label

    updated, old = replace_top_level_label(raw, value)
    if not only_to_review(old):
        raise RuntimeError("document label changed during classification; skipping write")
    path.write_text(updated, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--documents-dir", type=Path, default=ROOT / "data/documents")
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS,
                        help="classifier JSONL cache/results file")
    parser.add_argument("--dry-run", action="store_true", help="show proposed labels without writing documents")
    parser.add_argument("--limit", type=int, help="process at most this many eligible documents")
    args = parser.parse_args()

    results_path = args.results if args.results.is_absolute() else ROOT / args.results

    candidates = []
    for path in sorted(args.documents_dir.glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"skip {path}: cannot read document: {exc}", file=sys.stderr)
            continue
        if doc.get("deleted") or not only_to_review(doc.get("label")):
            continue
        candidates.append(path)
    if args.limit is not None:
        candidates = candidates[:args.limit]

    failures = 0
    for path in candidates:
        path = path.resolve()
        command = [sys.executable, str(CLASSIFIER), "--document", str(path), "--output", str(results_path)]
        run = subprocess.run(command, cwd=ROOT)
        if run.returncode:
            failures += 1
            print(f"ERROR {path}: classifier exited with status {run.returncode}", file=sys.stderr)
            continue
        try:
            row = result_for(path, results_path)
            selected = [LABELS[key] for key in LABELS if row["probabilities"][key] > THRESHOLD]
            if not selected:
                print(f"{path}: no family above 25% (other={row['probabilities'].get('other', 0):.3f})")
                continue
            print(f"{path}: {', '.join(selected)}")
            if not args.dry_run:
                replace_label(path, selected)
        except Exception as exc:
            failures += 1
            print(f"ERROR {path}: {exc}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
