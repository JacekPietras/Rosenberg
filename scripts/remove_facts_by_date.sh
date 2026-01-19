#!/bin/bash

# Remove facts from facts.json that match a specific date
# Usage: ./remove_facts_by_date.sh YYYY-MM-DD
#    or: ./remove_facts_by_date.sh YYYY

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

# Create backup
BACKUP_FILE="${FACTS_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
cp "$FACTS_FILE" "$BACKUP_FILE"
echo "Created backup: $BACKUP_FILE"

# Count facts before removal
BEFORE_COUNT=$(jq 'length' "$FACTS_FILE")
MATCHING_COUNT=$(jq --arg date "$DATE" '[.[] | select(.date == $date)] | length' "$FACTS_FILE")

if [ "$MATCHING_COUNT" -eq 0 ]; then
    echo "No facts found with date: $DATE"
    rm "$BACKUP_FILE"
    exit 0
fi

echo "Found $MATCHING_COUNT fact(s) with date: $DATE"
echo ""
echo "Facts to be removed:"
jq --arg date "$DATE" '[.[] | select(.date == $date)]' "$FACTS_FILE"
echo ""

# Remove facts with matching date
jq --arg date "$DATE" '[.[] | select(.date != $date)]' "$FACTS_FILE" > "${FACTS_FILE}.tmp"
mv "${FACTS_FILE}.tmp" "$FACTS_FILE"

# Count facts after removal
AFTER_COUNT=$(jq 'length' "$FACTS_FILE")
REMOVED_COUNT=$((BEFORE_COUNT - AFTER_COUNT))

echo "Removed $REMOVED_COUNT fact(s) from $FACTS_FILE"
echo "Facts before: $BEFORE_COUNT"
echo "Facts after: $AFTER_COUNT"

