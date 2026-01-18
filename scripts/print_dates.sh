#!/bin/bash

# Print all dates from data/facts.json (just the date values)

# Get the script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Path to facts.json
FACTS_FILE="$PROJECT_ROOT/data/facts.json"

# Check if facts.json exists
if [ ! -f "$FACTS_FILE" ]; then
    echo "Error: $FACTS_FILE not found"
    exit 1
fi

# Extract and print just the date values using jq
jq -r '.[].date' "$FACTS_FILE"

