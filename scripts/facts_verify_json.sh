#!/bin/bash
set -e

FACTS_FILE="data/facts.json"

echo "Validating JSON syntax..."
if ! jq '.' "$FACTS_FILE" > /dev/null 2>&1; then
    echo "ERROR: Invalid JSON syntax"
    exit 1
fi
echo "✓ JSON syntax valid"

echo "Checking required fields and structure..."
if ! jq -e 'if type != "array" then error("Root must be array") else . end |
  map(select(
    (has("source") | not) or
    (has("date") | not) or
    (has("facts") | not) or
    (.facts | type != "array")
  )) |
  if length > 0 then error("Found entries with missing/invalid fields") else empty end' \
  "$FACTS_FILE" > /dev/null 2>&1; then
    echo "✓ All entries have required fields"
else
    echo "ERROR: Some entries missing required fields"
    exit 1
fi

echo "Verifying date formats..."
if ! jq -e 'map(select(.date | test("^[0-9]{4}(-[0-9]{2}-[0-9]{2})?$") | not)) |
  if length > 0 then error("Found invalid date formats") else empty end' \
  "$FACTS_FILE" > /dev/null 2>&1; then
    echo "✓ All dates in valid format"
else
    echo "ERROR: Some dates have invalid format"
    exit 1
fi

echo "✓ All validation checks passed!"
