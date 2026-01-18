#!/bin/bash

# Compare dates from facts.json and letter filenames
# Generates a comparison document showing which dates exist in both, only in facts, or only in letters

# Get the script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Output file
OUTPUT_FILE="$PROJECT_ROOT/data/date_comparison.md"

# Temporary files
FACTS_DATA=$(mktemp)
LETTER_DATA=$(mktemp)
FACTS_DATES=$(mktemp)
LETTER_DATES=$(mktemp)
ALL_DATES=$(mktemp)

# Cleanup on exit
trap "rm -f $FACTS_DATA $LETTER_DATA $FACTS_DATES $LETTER_DATES $ALL_DATES" EXIT

echo "Collecting dates from facts.json..."
"$SCRIPT_DIR/print_fact_dates.sh" > "$FACTS_DATA"

echo "Collecting dates from letter filenames..."
"$SCRIPT_DIR/print_letter_dates.sh" > "$LETTER_DATA"

# Extract just the dates (first field before |) and sort them
cut -d'|' -f1 "$FACTS_DATA" | sed 's/ *$//' | sort > "$FACTS_DATES"
cut -d'|' -f1 "$LETTER_DATA" | sed 's/ *$//' | sort > "$LETTER_DATES"

# Combine and sort all unique dates
cat "$FACTS_DATES" "$LETTER_DATES" | sort -u > "$ALL_DATES"

# Count statistics
TOTAL_FACTS=$(wc -l < "$FACTS_DATES" | tr -d ' ')
TOTAL_LETTERS=$(wc -l < "$LETTER_DATES" | tr -d ' ')
TOTAL_UNIQUE=$(wc -l < "$ALL_DATES" | tr -d ' ')

# Find dates in both
IN_BOTH=$(comm -12 "$FACTS_DATES" "$LETTER_DATES" | wc -l | tr -d ' ')

# Find dates only in facts
ONLY_FACTS=$(comm -23 "$FACTS_DATES" "$LETTER_DATES" | wc -l | tr -d ' ')

# Find dates only in letters
ONLY_LETTERS=$(comm -13 "$FACTS_DATES" "$LETTER_DATES" | wc -l | tr -d ' ')

echo "Generating comparison document..."

# Generate the markdown document
cat > "$OUTPUT_FILE" << 'EOF'
# Date Comparison: Facts vs Letters

This document compares dates from `data/facts.json` (facts dates) with dates extracted from letter filenames in `data/letters/original/` (letter dates).

EOF

# Add statistics
cat >> "$OUTPUT_FILE" << EOF
## Statistics

- **Total facts entries**: $TOTAL_FACTS
- **Total letter files**: $TOTAL_LETTERS
- **Total unique dates**: $TOTAL_UNIQUE
- **Dates in both**: $IN_BOTH
- **Dates only in facts**: $ONLY_FACTS
- **Dates only in letters**: $ONLY_LETTERS

EOF

# Add dates in both
cat >> "$OUTPUT_FILE" << 'EOF'
## Dates in Both Facts and Letters

These dates appear in both `facts.json` and as letter filenames:

EOF

comm -12 "$FACTS_DATES" "$LETTER_DATES" | while read -r date; do
    # Find the fact source
    fact_source=$(grep "^$date |" "$FACTS_DATA" | head -1 | cut -d'|' -f2- | sed 's/^ *//')

    # Find the letter source(s)
    letter_info=$(grep "^$date |" "$LETTER_DATA")
    letter_sources=$(echo "$letter_info" | cut -d'|' -f3- | sed 's/^ *//' | paste -sd " / " -)

    echo "### Date: \`$date\`" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    echo "- **Facts Source:** $fact_source" >> "$OUTPUT_FILE"
    echo "- **Letter Source:** $letter_sources" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
done

# Add dates only in facts
cat >> "$OUTPUT_FILE" << 'EOF'

## Dates Only in Facts

These dates appear in `facts.json` but have no corresponding letter file:

EOF

comm -23 "$FACTS_DATES" "$LETTER_DATES" | while read -r date; do
    fact_source=$(grep "^$date |" "$FACTS_DATA" | head -1 | cut -d'|' -f2- | sed 's/^ *//')
    echo "- **\`$date\`** - $fact_source" >> "$OUTPUT_FILE"
done

# Add dates only in letters
cat >> "$OUTPUT_FILE" << 'EOF'

## Dates Only in Letters

These dates have letter files but no corresponding entries in `facts.json`:

EOF

comm -13 "$FACTS_DATES" "$LETTER_DATES" | while read -r date; do
    # Find the letter filename(s) and source(s)
    letter_info=$(grep "^$date |" "$LETTER_DATA")
    letter_filenames=$(echo "$letter_info" | cut -d'|' -f2 | sed 's/^ *//;s/ *$//' | paste -sd ", " -)
    letter_sources=$(echo "$letter_info" | cut -d'|' -f3- | sed 's/^ *//' | paste -sd " / " -)
    echo "- **\`$date\`** - File: \`$letter_filenames.md\` - Source: $letter_sources" >> "$OUTPUT_FILE"
done

# Add footer
cat >> "$OUTPUT_FILE" << EOF
