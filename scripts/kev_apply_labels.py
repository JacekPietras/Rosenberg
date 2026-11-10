#!/usr/bin/env python3
"""Apply only independently validated Kev labels; default mode is a dry run."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import stat
import sys
import tempfile
from pathlib import Path

from kev_classify_documents import h, state
from kev_source_guards import accepted_prediction

ROOT = Path(__file__).resolve().parents[1]
FAMILIES = {
    "franconian": "new",
    "schenk": "Schenk",
    "monch": "Mönch",
    "rorschach": "Rorschach",
    "czech": "Czechia",
}
ALL_FAMILY_LABELS = set(FAMILIES.values())


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_jsonl(path: Path):
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{number}: invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{number}: each JSONL row must be an object")
        rows.append(row)
    return rows


def verify_frozen_files(config: dict, guard_freeze: dict, freeze_path: Path) -> dict:
    artifacts = guard_freeze.get("frozen_artifacts", {})
    if not artifacts:
        raise ValueError("guard freeze is missing frozen_artifacts")
    expected_files = {
        "guard_code_sha256": ROOT / "scripts/kev_source_guards.py",
        "runner_code_sha256": ROOT / "scripts/kev_classify_documents.py",
        "names_md_sha256": ROOT / "data/names.md",
        "places_json_sha256": ROOT / "data/places.json",
    }
    actual = {}
    for key, file_path in expected_files.items():
        actual[key] = sha256_file(file_path)
        if artifacts.get(key) != actual[key]:
            raise ValueError(f"frozen {key} does not match current file {file_path}")
    if config.get("model_fingerprint") != guard_freeze.get("frozen_model_fingerprint"):
        raise ValueError("model fingerprint differs between config and guard freeze")
    if config.get("prompt_hash") != guard_freeze.get("frozen_prompt_hash"):
        raise ValueError("prompt hash differs between config and guard freeze")
    calculated_prompt_hash = h({"reference": config.get("reference"),
                                "question": config.get("question", "Which historical family is substantively represented in this document?"),
                                "criteria": config.get("criteria")})
    if calculated_prompt_hash != config.get("prompt_hash"):
        raise ValueError("prompt contents do not match the frozen prompt hash")
    if config.get("acceptance_threshold") != guard_freeze.get("frozen_probability_threshold"):
        raise ValueError("probability threshold differs from guard freeze")
    if config.get("minimum_margin") != guard_freeze.get("frozen_minimum_margin"):
        raise ValueError("minimum margin differs from guard freeze")
    if config.get("eligible_choices") != guard_freeze.get("eligible_families"):
        raise ValueError("eligible family list differs from guard freeze")
    return {"guard_freeze_path": str(freeze_path), **actual}


def validate_gate(validation: dict, config: dict, guard_freeze: dict, current_hashes: dict):
    if validation.get("gate_passed") is not True:
        raise ValueError("validation gate_passed must be true")
    accepted_total = validation.get("accepted")
    if isinstance(accepted_total, bool) or not isinstance(accepted_total, int) or accepted_total < 40:
        raise ValueError("validation accepted count is below 40")
    if type(validation.get("accepted_errors")) is not int or validation["accepted_errors"] != 0:
        raise ValueError("validation accepted_errors must equal zero")
    enabled = validation.get("enabled_families")
    if (not isinstance(enabled, list) or len(enabled) < 3 or
            any(not isinstance(family, str) for family in enabled) or len(set(enabled)) != len(enabled)):
        raise ValueError("validation must enable at least three distinct families")
    if any(family not in FAMILIES for family in enabled):
        raise ValueError("validation enabled_families contains an unknown class")
    counts = validation.get("accepted_by_family")
    if not isinstance(counts, dict):
        raise ValueError("validation is missing accepted_by_family counts")
    for family in enabled:
        if isinstance(counts.get(family), bool) or not isinstance(counts.get(family), int) or counts[family] < 8:
            raise ValueError(f"enabled family {family!r} has fewer than 8 accepted validation cases")
    if validation.get("model_fingerprint") != config.get("model_fingerprint"):
        raise ValueError("validation model fingerprint does not match frozen config")
    if validation.get("prompt_hash") != config.get("prompt_hash"):
        raise ValueError("validation prompt hash does not match frozen config")
    frozen_guard_hash = current_hashes["guard_code_sha256"]
    if validation.get("guard_sha256") != frozen_guard_hash:
        raise ValueError("validation guard_sha256 does not match frozen guard code")
    if guard_freeze.get("frozen_model_fingerprint") != validation.get("model_fingerprint"):
        raise ValueError("validation model fingerprint does not match guard freeze")
    if guard_freeze.get("frozen_prompt_hash") != validation.get("prompt_hash"):
        raise ValueError("validation prompt hash does not match guard freeze")
    if accepted_total < sum(counts[f] for f in enabled):
        raise ValueError("validation accepted total is smaller than enabled family counts")
    validation_cases = validation.get("validation_cases")
    if isinstance(validation_cases, bool) or not isinstance(validation_cases, int) or validation_cases < 180:
        raise ValueError("validation must describe at least 180 confirmation cases")
    return enabled


def top_level_label_value_start(raw: str) -> tuple[int, int, object]:
    """Locate only the top-level label value, never a nested entry label."""
    decoder = json.JSONDecoder()
    pos = 0
    while pos < len(raw) and raw[pos].isspace():
        pos += 1
    if pos >= len(raw) or raw[pos] != "{":
        raise ValueError("document root must be an object")
    pos += 1
    while True:
        while pos < len(raw) and (raw[pos].isspace() or raw[pos] == ","):
            pos += 1
        if pos >= len(raw) or raw[pos] == "}":
            break
        key, end_key = decoder.raw_decode(raw, pos)
        if not isinstance(key, str):
            raise ValueError("top-level object key must be a string")
        pos = end_key
        while pos < len(raw) and raw[pos].isspace():
            pos += 1
        if pos >= len(raw) or raw[pos] != ":":
            raise ValueError("expected colon after top-level key")
        pos += 1
        while pos < len(raw) and raw[pos].isspace():
            pos += 1
        start = pos
        value, end = decoder.raw_decode(raw, pos)
        if key == "label":
            return start, end, value
        pos = end
        while pos < len(raw) and raw[pos].isspace():
            pos += 1
        if pos < len(raw) and raw[pos] == "}":
            break
    raise ValueError("document has no top-level label field")


def new_labels(old_label, target: str):
    if isinstance(old_label, str):
        if old_label != "to review":
            raise ValueError("top-level string label is no longer 'to review'")
        return target
    if not isinstance(old_label, list) or any(not isinstance(v, str) for v in old_label):
        raise ValueError("top-level label must be a string or array of strings")
    existing_families = set(old_label) & ALL_FAMILY_LABELS
    conflicts = existing_families - {target}
    if conflicts:
        raise ValueError("document already has a different family label: " + ", ".join(sorted(conflicts)))
    out = [v for v in old_label if v != "to review"]
    if target not in out:
        # Replace the review marker in place to retain label order where possible.
        try:
            index = old_label.index("to review")
            insert_at = sum(1 for v in old_label[:index] if v != "to review")
        except ValueError:
            insert_at = len(out)
        out.insert(insert_at, target)
    return out


def replace_top_level_label(raw: str, label) -> tuple[str, object]:
    start, end, old = top_level_label_value_start(raw)
    replacement = json.dumps(label, ensure_ascii=False)
    updated = raw[:start] + replacement + raw[end:]
    before = json.loads(raw)
    after = json.loads(updated)
    expected = copy.deepcopy(before)
    expected["label"] = label
    if after != expected:
        raise ValueError("label-only replacement changed fields outside top-level label")
    return updated, old


def active_to_review(doc: dict) -> bool:
    labels = doc.get("label")
    return not doc.get("deleted") and "to review" in (labels if isinstance(labels, list) else [labels])


def valid_probabilities(row: dict) -> bool:
    probs = row.get("probabilities")
    label = row.get("prediction")
    if not isinstance(probs, dict) or label not in probs or len(probs) < 2:
        return False
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1
           for v in probs.values()):
        return False
    vals = sorted(probs.values(), reverse=True)
    return abs(sum(vals) - 1) <= .005 and probs[label] >= vals[0] - .005


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", required=True, help="Kev classifier JSONL results")
    ap.add_argument("--config", required=True, help="Frozen prompt/config JSON")
    ap.add_argument("--validation", required=True, help="Parent validation gate assessment JSON")
    ap.add_argument("--output", required=True, help="Append-only audit receipt JSONL")
    ap.add_argument("--guard-freeze-path", default="reports/kev-improvement/guard-selection.json")
    ap.add_argument("--apply", action="store_true", help="Write eligible labels after all gate and integrity checks")
    args = ap.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    guard_freeze_path = Path(args.guard_freeze_path)
    guard_freeze = json.loads(guard_freeze_path.read_text(encoding="utf-8"))
    validation = json.loads(Path(args.validation).read_text(encoding="utf-8"))
    frozen_hashes = verify_frozen_files(config, guard_freeze, guard_freeze_path)
    enabled_families = validate_gate(validation, config, guard_freeze, frozen_hashes)
    cfg = dict(config, eligible_choices=enabled_families)

    rows = load_jsonl(Path(args.results))
    latest = {}
    for row in rows:
        path_value = row.get("path")
        if isinstance(path_value, str):
            path = Path(path_value)
            if not path.is_absolute():
                path = ROOT / path
            latest[str(path.resolve())] = row

    audit_path = Path(args.output)
    docs_root = (ROOT / "data/documents").resolve()
    try:
        audit_path.resolve().relative_to(docs_root)
        raise ValueError("audit output must not be written inside data/documents")
    except ValueError as exc:
        if str(exc).startswith("audit output"):
            raise
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with audit_path.open("a", encoding="utf-8") as audit:
        for path_string, row in latest.items():
            doc_path = Path(path_string)
            receipt = {
                "path": path_string,
                "case_id": row.get("case_id"),
                "prediction": row.get("prediction"),
                "input_sha256": row.get("input_sha256"),
                "source_fingerprint": row.get("source_fingerprint"),
                "model_fingerprint": row.get("model_fingerprint"),
                "prompt_hash": row.get("prompt_hash"),
                "validation_cases": validation.get("validation_cases"),
                "status": "skipped",
                "before_labels": None,
                "after_labels": None,
            }
            reason = None
            if row.get("status") != "ok":
                reason = "latest result row is not successful"
            elif not valid_probabilities(row):
                reason = "result probabilities are malformed or prediction is not the top choice"
            elif row.get("model_fingerprint") != config.get("model_fingerprint"):
                reason = "result model fingerprint differs from frozen config"
            elif row.get("prompt_hash") != config.get("prompt_hash"):
                reason = "result prompt hash differs from frozen config"
            elif row.get("prediction") not in enabled_families:
                reason = "predicted family is not enabled by validation"
            elif not doc_path.exists():
                reason = "source document path does not exist"
            if reason:
                receipt["reason"] = reason
                audit.write(json.dumps(receipt, ensure_ascii=False) + "\n")
                continue

            original_raw = doc_path.read_text(encoding="utf-8")
            try:
                if args.apply:
                    try:
                        doc_path.resolve().relative_to(docs_root)
                    except ValueError:
                        raise ValueError("apply is restricted to data/documents")
                doc = json.loads(original_raw)
                if not active_to_review(doc):
                    raise ValueError("document is not active and labeled to review")
                current_state = state(doc, config.get("reference"))
                current_fingerprint = h(current_state)
                if current_fingerprint != row.get("source_fingerprint"):
                    raise ValueError("source fingerprint is stale")
                compact_state = json.dumps(current_state, ensure_ascii=False)
                current_input_sha = hashlib.sha256(compact_state.encode("utf-8")).hexdigest()
                if row.get("input_sha256") != current_input_sha:
                    raise ValueError("model input hash is stale")
                accepted, guard_reason = accepted_prediction(doc, row, cfg)
                if not accepted:
                    raise ValueError("source guard rejected result: " + guard_reason)
                target = FAMILIES[row["prediction"]]
                labels = doc.get("label")
                receipt["before_labels"] = labels
                new_label = new_labels(labels, target)
                updated_raw, old_label = replace_top_level_label(original_raw, new_label)
                if old_label != labels:
                    raise ValueError("raw top-level label does not match parsed document")
                updated = json.loads(updated_raw)
                if updated.get("label") != new_label:
                    raise ValueError("serialized label did not round-trip")
                receipt["after_labels"] = new_label
                receipt["reason"] = "eligible validated label; source, model, prompt, and guard checks passed"

                if args.apply:
                    # Re-read immediately before the atomic replace to avoid overwriting concurrent edits.
                    if doc_path.read_text(encoding="utf-8") != original_raw:
                        raise ValueError("document changed after validation; concurrent edit detected")
                    latest_doc = json.loads(doc_path.read_text(encoding="utf-8"))
                    if not active_to_review(latest_doc) or h(state(latest_doc, config.get("reference"))) != current_fingerprint:
                        raise ValueError("document status or source changed before write")
                    fd, temp_name = tempfile.mkstemp(prefix=doc_path.name + ".", suffix=".tmp", dir=doc_path.parent)
                    try:
                        os.chmod(temp_name, stat.S_IMODE(doc_path.stat().st_mode))
                        with os.fdopen(fd, "w", encoding="utf-8", newline="") as temp:
                            temp.write(updated_raw)
                            temp.flush()
                            os.fsync(temp.fileno())
                        os.replace(temp_name, doc_path)
                    finally:
                        if os.path.exists(temp_name):
                            os.unlink(temp_name)
                    receipt["status"] = "applied"
                    written += 1
                else:
                    receipt["status"] = "dry_run"
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                receipt["reason"] = str(exc)
            audit.write(json.dumps(receipt, ensure_ascii=False) + "\n")

    print(json.dumps({"apply": args.apply, "latest_paths": len(latest), "written": written,
                      "enabled_families": enabled_families, "audit": str(audit_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
