#!/bin/bash
# Helper script to remove a processed letter from the report
# Usage: ./remove_letter_from_report.sh "filename.md"

set -e

if [ $# -ne 1 ]; then
    echo "Usage: $0 <filename>"
    exit 1
fi

LETTER_FILENAME="$1"
REPORT_FILE="reports/dates_only_in_letters.md"

if [ ! -f "$REPORT_FILE" ]; then
    echo "ERROR: Report file not found: $REPORT_FILE"
    exit 1
fi

echo "Removing '$LETTER_FILENAME' from report..."

# Escape special characters for sed
ESCAPED_FILENAME=$(echo "$LETTER_FILENAME" | sed 's/[]\/$*.^[]/\\&/g')

# Remove the line containing this filename
sed -i '' "/File: \`$ESCAPED_FILENAME\`/d" "$REPORT_FILE"

# Update the total count
REMAINING=$(grep -cE "^- \*\*\`[0-9-]+\`\*\*" "$REPORT_FILE" || echo "0")
sed -i '' "s/\*\*Total\*\*: [0-9]\+/**Total**: $REMAINING/" "$REPORT_FILE"

# Update timestamp
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
sed -i '' "s/\*Generated on.*/*Generated on $TIMESTAMP*/" "$REPORT_FILE"

echo "✓ Removed from report. Remaining: $REMAINING letters"
exit 0
