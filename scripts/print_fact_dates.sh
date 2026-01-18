#!/bin/bash

# Print all dates from data/facts.json with their sources
# Format: date | source

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

# Extract and print date and source using jq
jq -r '.[] | "\(.date) | \(.source)"' "$FACTS_FILE"

