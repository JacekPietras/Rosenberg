#!/usr/bin/env python3
"""Run the validated local Kev workflow; label writes require --apply."""
import argparse
import collections
import datetime
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, default=ROOT / "reports/kev-improvement")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    config_path = work / "frozen-config.json"
    validation_path = work / "application-validation.json"
    results = work / "backlog-results.jsonl"
    audit = work / ("backlog-applied.jsonl" if args.apply else "backlog-dry-run.jsonl")
    status_path = work / "backlog-status.json"
    status = {"apply": args.apply, "started_utc": datetime.datetime.now(datetime.UTC).isoformat()}

    def update(stage, **extra):
        status.update(stage=stage, **extra)
        status["updated_utc"] = datetime.datetime.now(datetime.UTC).isoformat()
        temporary = status_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(status, indent=2) + "\n")
        temporary.replace(status_path)
        print(stage, flush=True)

    def run(script, arguments, log_name):
        with (work / log_name).open("w") as log:
            subprocess.run([sys.executable, str(ROOT / "scripts" / "kev" / script), *arguments],
                           cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)

    common = ["--results", str(results), "--config", str(config_path),
              "--validation", str(validation_path), "--output", str(audit)]
    try:
        # Verify the gate and frozen artifacts before spending time on inference.
        update("checking_validation")
        run("kev_apply_labels.py", common, "backlog-preflight.log")
        update("scoring")
        run("kev_classify_documents.py", ["--config", str(config_path), "--source-guards",
                                          "--output", str(results)], "backlog-progress.log")
        inference = json.loads(Path(str(results) + ".summary.json").read_text())
        update("applying" if args.apply else "checking_proposals", inference_errors=inference["errors"])
        run("kev_apply_labels.py", common + (["--apply"] if args.apply else []), "backlog-apply.log")
        receipts = [json.loads(line) for line in audit.read_text().splitlines() if line.strip()]
        applied = {row["path"]: row for row in receipts if row.get("status") == "applied"}
        update("validating", applied_documents=len(applied))
        if applied:
            # The repository validator can normalize files; run it on isolated copies.
            with tempfile.TemporaryDirectory(prefix="kev-label-validation-") as temp:
                for source in applied:
                    shutil.copyfile(source, Path(temp) / Path(source).name)
                run("validate_documents.py", [temp], "backlog-validation.log")
            subprocess.run(["git", "diff", "--check", "--", *applied], cwd=ROOT, check=True)
        remaining = 0
        for path in (ROOT / "data/documents").glob("*.json"):
            doc = json.loads(path.read_text())
            labels = doc.get("label", [])
            if isinstance(labels, str):
                labels = [labels]
            remaining += not doc.get("deleted") and "to review" in labels
        counts = collections.Counter(row["prediction"] for row in applied.values())
        update("partial" if inference["errors"] else "complete", applied_documents=len(applied),
               applied_by_family=dict(counts), remaining_to_review=remaining,
               inference_cases=inference["cases"])
        return 2 if inference["errors"] else 0
    except Exception as exc:
        update("failed", error=str(exc))
        raise


if __name__ == "__main__":
    sys.exit(main())
