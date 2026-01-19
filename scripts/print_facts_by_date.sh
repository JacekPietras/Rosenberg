#!/bin/bash

# Print facts from facts.json that match a specific date
# Usage: ./print_facts_by_date.sh YYYY-MM-DD
#    or: ./print_facts_by_date.sh YYYY

set -e

if [ $# -eq 0 ]; then
    echo "Usage: $0 <date>"
    echo "  Date format: YYYY-MM-DD or YYYY"
    echo "  Example: $0 1327-05-04"
    echo "  Example: $0 1327"
    exit 1
fi

DATE="$1"
FACTS_FILE="data/facts.json"

if [ ! -f "$FACTS_FILE" ]; then
    echo "Error: $FACTS_FILE not found"
    exit 1
fi

# Use jq to filter facts by date and pretty-print them
jq --arg date "$DATE" '[.[] | select(.date == $date)]' "$FACTS_FILE"

