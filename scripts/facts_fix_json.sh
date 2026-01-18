#!/bin/bash
set -e

FACTS_FILE="data/facts.json"
TMP_FILE="data/facts.json.tmp"

echo "Auto-formatting JSON with jq..."
jq '.' "$FACTS_FILE" > "$TMP_FILE" && mv "$TMP_FILE" "$FACTS_FILE"

echo "✓ JSON syntax corrected and formatted"
echo "Re-running validation..."
./scripts/facts_verify_json.sh
