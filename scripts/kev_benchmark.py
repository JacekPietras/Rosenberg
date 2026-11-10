#!/usr/bin/env python3
"""Exploratory document-label benchmark client for a local Kev server."""

import argparse
import hashlib
import json
import math
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

MODEL_DEFAULT = "kev-latest"
REFERENCE = ("Classify family relevance from the historical source text, not from a surname or place name alone. "
             "Franconian target: the primary medieval von Rosenberg family in Franconia/Odenwald, associated with Boxberg, "
             "Haltenbergstetten, and Schüpf; a place by itself is insufficient. Schenk and Mönch/Münch von Rosenberg are "
             "separate families. Swiss Rorschach target: the Swiss Rorschach/Rosenberg family, including Eglolf von Rorschach "
             "and its Herisau/Zuckenriet context; a place alone is insufficient. Czech target: the historical South Bohemian "
             "Rožmberk/Rosenberg dynasty, including Vok, Peter, and Jodok, associated with Hohenfurt and Krumau; unrelated "
             "Czech people or institutions do not qualify. Orsini-Rosenberg means the modern house. Categories are independent "
             "except unrelated: unrelated is true only when none of the six families is substantively relevant, and cannot "
             "coexist with a positive family category. A coincidental surname or place mention alone is unrelated.")
QUESTIONS = {
    "franconian": "Does the source substantively concern the primary medieval Franconian/Odenwald von Rosenberg family, one of its members, or a direct interaction with it? A place or surname alone is not enough. Do not count the separate Schenk or Mönch/Münch families.",
    "schenk": "Does the source substantively concern the separate Schenk von Rosenberg family, one of its members, or a direct interaction with it? A surname alone is not enough.",
    "monch": "Does the source substantively concern the separate Mönch/Münch von Rosenberg family, one of its members, or a direct interaction with it? A surname alone is not enough.",
    "rorschach": "Does the source substantively concern the Swiss Rorschach/Rosenberg family or one of its members (for example Eglolf von Rorschach)? A Rorschach place alone is not enough; do not count the Franconian or Czech families.",
    "czech": "Does the source substantively concern the historical South Bohemian Rožmberk/Rosenberg dynasty or one of its members (for example Vok, Peter, or Jodok)? Czech institutions, people, or places alone do not qualify.",
    "orsini": "Does the source substantively concern the modern Orsini-Rosenberg house or one of its members? A coincidental surname/place mention alone is not enough.",
    "unrelated": "Is the source unrelated to all six family categories in the shared reference? Answer yes only if none is substantively relevant. A coincidental surname or place mention alone counts as unrelated. This category cannot coexist with a positive family category.",
}
TEXT_FIELDS = ("german", "latin", "summary", "english")


def canonical_hash(value):
    blob = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def doc_state(doc):
    state = {"reference": REFERENCE, "date": doc.get("date"), "place": doc.get("place"), "entries": []}
    for entry in doc.get("entries", []):
        item = {k: entry[k] for k in ("source", "url", "title") if k in entry}
        item.update({k: entry[k] for k in TEXT_FIELDS if isinstance(entry.get(k), str) and entry[k]})
        state["entries"].append(item)
    return state


def request_model(base_url, model, state, timeout):
    payload = {"model": model, "state": json.dumps(state, ensure_ascii=False),
               "questions": {k: {"type": "noul", "instructions": v,
                                 "criteria": {"true": "Yes, the criterion is met.", "false": "No, the criterion is not met."}}
                            for k, v in QUESTIONS.items()}}
    req = urllib.request.Request(base_url.rstrip("/") + "/v1/systemone",
                                 data=json.dumps(payload, ensure_ascii=False).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            status = response.status
            request_id = response.headers.get("x-typesafe-request-id")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail[:2000]}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"request failed: {exc}") from exc
    latency = time.monotonic() - start
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"HTTP {status}: response is not JSON: {body[:500]}") from exc
    answers = data.get("answers")
    if not isinstance(answers, dict):
        raise RuntimeError(f"HTTP {status}: missing answers object")
    probabilities = {}
    for key in QUESTIONS:
        answer = answers.get(key)
        value = answer.get("noul") if isinstance(answer, dict) else None
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
            raise RuntimeError(f"HTTP {status}: answers.{key}.noul missing or invalid")
        probabilities[key] = float(value)
    return probabilities, latency, data, request_id


def get_model_card(base_url, model, timeout):
    req = urllib.request.Request(base_url.rstrip("/") + "/v1/models")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"GET /v1/models failed: {exc}") from exc
    cards = payload.get("models")
    if not isinstance(cards, list):
        raise RuntimeError("GET /v1/models: missing models list")
    card = next((item for item in cards if isinstance(item, dict) and item.get("name") == model), None)
    if card is None:
        raise RuntimeError(f"GET /v1/models: requested model {model!r} is not listed")
    identity_fields = ("name", "run", "base", "lora", "device", "backend", "dtype", "temperature", "release_date")
    identity = {key: card.get(key) for key in identity_fields}
    return card, canonical_hash(identity)


def read_cases(path):
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{number}: invalid JSON: {exc}") from exc
        if not isinstance(case.get("path"), str) or not isinstance(case.get("expected"), dict):
            raise ValueError(f"{path}:{number}: each case needs path and expected object")
        for k, v in case["expected"].items():
            if k not in QUESTIONS or not isinstance(v, bool):
                raise ValueError(f"{path}:{number}: expected must map known question names to booleans")
        yield case


def score(records, threshold):
    results = {}
    for q in QUESTIONS:
        vals = [(r["probabilities"][q], r["expected"][q]) for r in records if q in r["expected"]]
        if not vals:
            continue
        tp = sum(p >= .5 and y for p, y in vals); tn = sum(p < .5 and not y for p, y in vals)
        fp = sum(p >= .5 and not y for p, y in vals); fn = sum(p < .5 and y for p, y in vals)
        thresholds = {}
        for t in (0.8, 0.9, 0.95, 0.99):
            confident = [(p, y) for p, y in vals if p >= t or p <= 1 - t]
            err = sum((p >= .5) != y for p, y in confident)
            thresholds[str(t)] = {"coverage": len(confident) / len(vals), "error_rate": err / len(confident) if confident else None}
        results[q] = {"n": len(vals), "accuracy_at_0.5": (tp + tn) / len(vals), "brier": sum((p - int(y)) ** 2 for p, y in vals) / len(vals),
                      "confusion_at_0.5": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
                      "exploratory_confidence": thresholds}
    allq = [(r, [q for q in QUESTIONS if q in r["expected"]]) for r in records]
    complete = [(r, qs) for r, qs in allq if len(qs) == len(QUESTIONS)]
    confident = [(r, qs) for r, qs in complete if all(max(r["probabilities"][q], 1-r["probabilities"][q]) >= threshold for q in qs)]
    errors = sum(any((r["probabilities"][q] >= .5) != r["expected"][q] for q in qs) for r, qs in confident)
    results["all_questions_per_document"] = {"complete_n": len(complete), "confident_coverage": len(confident) / len(complete) if complete else None,
                                                 "error_rate_on_confident": errors / len(confident) if confident else None}
    results["caution"] = "Exploratory benchmark only. Confidence thresholds and error rates are not validated or calibrated. Multiple categories may all be positive."
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cases", required=True, help="JSONL cases: path and expected question booleans")
    ap.add_argument("--base-url", default="http://127.0.0.1:8009")
    ap.add_argument("--model", default=MODEL_DEFAULT)
    ap.add_argument("--output", default="/tmp/rosenberg-kev-benchmark.jsonl")
    ap.add_argument("--timeout", type=float, default=180)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--threshold", type=float, default=.9)
    args = ap.parse_args()
    if not 0 < args.threshold < 1:
        ap.error("--threshold must be between 0 and 1")
    out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
    qhash = canonical_hash({"reference": REFERENCE, "questions": QUESTIONS})
    model_card, model_fingerprint = get_model_card(args.base_url, args.model, args.timeout)
    cache = {}
    if out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
                if row.get("status") == "ok":
                    cache[(row.get("case_id"), row.get("source_fingerprint"), row.get("questions_hash"), row.get("model_fingerprint"))] = row
            except (json.JSONDecodeError, TypeError):
                continue
    rows = []
    for i, case in enumerate(read_cases(args.cases)):
        if args.limit is not None and i >= args.limit: break
        path = Path(case["path"])
        if not path.is_absolute(): path = Path.cwd() / path
        doc = json.loads(path.read_text(encoding="utf-8")); state = doc_state(doc)
        fingerprint = canonical_hash(state)
        case_id = case.get("id", str(path))
        key = (case_id, fingerprint, qhash, model_fingerprint)
        row = cache.get(key)
        if row is None:
            try:
                probs, latency, response, request_id = request_model(args.base_url, args.model, state, args.timeout)
                row = {"case_id": case_id, "path": str(path), "source_fingerprint": fingerprint, "questions_hash": qhash,
                       "model": args.model, "model_id": response.get("model"), "model_fingerprint": model_fingerprint,
                       "model_card": model_card, "request_id": request_id, "raw_response": response, "expected": case["expected"],
                       "probabilities": probs, "latency_seconds": latency, "state_characters": len(json.dumps(state, ensure_ascii=False)),
                       "status": "ok", "note": case.get("note"), "source_quote": case.get("source_quote")}
            except Exception as exc:
                row = {"case_id": case_id, "path": str(path), "source_fingerprint": fingerprint, "questions_hash": qhash,
                       "model": args.model, "model_fingerprint": model_fingerprint, "model_card": model_card,
                       "expected": case["expected"], "state_characters": len(json.dumps(state, ensure_ascii=False)),
                       "status": "error", "error": str(exc), "note": case.get("note"), "source_quote": case.get("source_quote")}
            with out.open("a", encoding="utf-8") as f: f.write(json.dumps(row, ensure_ascii=False) + "\n")
        else:
            # Gold labels and annotations may be refined independently of model input.
            row = dict(row, expected=case["expected"], note=case.get("note"), source_quote=case.get("source_quote"))
            with out.open("a", encoding="utf-8") as f: f.write(json.dumps(row, ensure_ascii=False) + "\n")
        rows.append(row)
        print(f"{case_id}: {row['status']}" + (f"; {row.get('error')}" if row["status"] == "error" else ""), file=sys.stderr)
    ok = [r for r in rows if r.get("status") == "ok"]
    summary = {"model": args.model, "model_fingerprint": model_fingerprint, "model_card": model_card,
               "base_url": args.base_url, "cases": len(rows), "successful": len(ok), "errors": len(rows)-len(ok),
               "metrics": score(ok, args.threshold)}
    summary_path = Path(str(out) + ".summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
