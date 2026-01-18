#!/bin/bash

# Compare dates from facts.json and letter filenames
# Generates 3 separate files showing which dates exist in both, only in facts, or only in letters

# Get the script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Create reports directory if it doesn't exist
REPORTS_DIR="$PROJECT_ROOT/reports"
mkdir -p "$REPORTS_DIR"

# Output files
OUTPUT_BOTH="$REPORTS_DIR/dates_in_both.md"
OUTPUT_ONLY_FACTS="$REPORTS_DIR/dates_only_in_facts.md"
OUTPUT_ONLY_LETTERS="$REPORTS_DIR/dates_only_in_letters.md"

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

echo "Generating comparison files..."

# ===== FILE 1: Dates in Both =====
cat > "$OUTPUT_BOTH" << 'EOF'
# Dates in Both Facts and Letters

These dates appear in both `data/facts.json` and as letter filenames.

EOF

cat >> "$OUTPUT_BOTH" << EOF
**Total**: $IN_BOTH dates

EOF

comm -12 "$FACTS_DATES" "$LETTER_DATES" | while read -r date; do
    # Find the fact source
    fact_source=$(grep "^$date |" "$FACTS_DATA" | head -1 | cut -d'|' -f2- | sed 's/^ *//')

    # Find the letter source(s)
    letter_info=$(grep "^$date |" "$LETTER_DATA")
    letter_sources=$(echo "$letter_info" | cut -d'|' -f3- | sed 's/^ *//' | paste -sd " / " -)

    echo "### Date: \`$date\`" >> "$OUTPUT_BOTH"
    echo "" >> "$OUTPUT_BOTH"
    echo "- **Facts Source:** $fact_source" >> "$OUTPUT_BOTH"
    echo "- **Letter Source:** $letter_sources" >> "$OUTPUT_BOTH"
    echo "" >> "$OUTPUT_BOTH"
done

cat >> "$OUTPUT_BOTH" << EOF

---

*Generated on $(date '+%Y-%m-%d %H:%M:%S')*
EOF

# ===== FILE 2: Dates Only in Facts =====
cat > "$OUTPUT_ONLY_FACTS" << 'EOF'
# Dates Only in Facts

These dates appear in `data/facts.json` but have no corresponding letter file.

EOF

cat >> "$OUTPUT_ONLY_FACTS" << EOF
**Total**: $ONLY_FACTS dates

EOF

comm -23 "$FACTS_DATES" "$LETTER_DATES" | while read -r date; do
    fact_source=$(grep "^$date |" "$FACTS_DATA" | head -1 | cut -d'|' -f2- | sed 's/^ *//')
    echo "- **\`$date\`** - $fact_source" >> "$OUTPUT_ONLY_FACTS"
done

cat >> "$OUTPUT_ONLY_FACTS" << EOF

---

*Generated on $(date '+%Y-%m-%d %H:%M:%S')*
EOF

# ===== FILE 3: Dates Only in Letters =====
cat > "$OUTPUT_ONLY_LETTERS" << 'EOF'
# Dates Only in Letters

These dates have letter files but no corresponding entries in `data/facts.json`.

EOF

cat >> "$OUTPUT_ONLY_LETTERS" << EOF
**Total**: $ONLY_LETTERS dates

EOF

comm -13 "$FACTS_DATES" "$LETTER_DATES" | while read -r date; do
    # Find the letter filename(s) and source(s) - output each on separate line
    grep "^$date |" "$LETTER_DATA" | while IFS='|' read -r date_field filename_field source_field; do
        filename=$(echo "$filename_field" | sed 's/^ *//;s/ *$//')
        source=$(echo "$source_field" | sed 's/^ *//')
        echo "- **\`$date\`** - File: \`$filename.md\` - Source: $source" >> "$OUTPUT_ONLY_LETTERS"
    done
done

cat >> "$OUTPUT_ONLY_LETTERS" << EOF

---

*Generated on $(date '+%Y-%m-%d %H:%M:%S')*
EOF

echo ""
echo "✅ Done. Generated 3 comparison files:"
echo "   - $OUTPUT_BOTH ($IN_BOTH dates)"
echo "   - $OUTPUT_ONLY_FACTS ($ONLY_FACTS dates)"
echo "   - $OUTPUT_ONLY_LETTERS ($ONLY_LETTERS dates)"
