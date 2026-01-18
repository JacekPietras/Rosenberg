#!/bin/bash
# Helper script to get information about the next letter to process
# Returns: filename, date, and source in a parseable format
# Exit code: 0 if letter found, 1 if no letters remaining

set -e

REPORT_FILE="reports/dates_only_in_letters.md"

# Check if report exists
if [ ! -f "$REPORT_FILE" ]; then
    echo "REPORT_MISSING"
    exit 1
fi

# Extract the first letter from the report
FIRST_LINE=$(grep -E "^- \*\*\`[0-9-]+\`\*\* - File:" "$REPORT_FILE" | head -1)

if [ -z "$FIRST_LINE" ]; then
    echo "NO_LETTERS"
    exit 1
fi

# Extract components
LETTER_FILENAME=$(echo "$FIRST_LINE" | sed -E 's/.*File: `([^`,]+).*/\1/')
DATE_CODE=$(echo "$FIRST_LINE" | sed -E 's/.*\*\*`([^`]+)`\*\*.*/\1/')
SOURCE=$(echo "$FIRST_LINE" | sed -E 's/.*Source: (.+)$/\1/')

# Output in parseable format (quote strings with spaces)
echo "FILENAME=\"$LETTER_FILENAME\""
echo "DATE=\"$DATE_CODE\""
echo "SOURCE=\"$SOURCE\""
echo "PATH=\"data/letters/$LETTER_FILENAME\""

exit 0
