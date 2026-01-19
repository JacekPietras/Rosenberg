#!/bin/bash
set -e

# Process a specific letter file for fact extraction
# This script coordinates the extraction workflow for a single letter file
#
# Usage: ./scripts/process_document.sh <filename>
# Example: ./scripts/process_document.sh "1327 may 4.md"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SEARCH_DIRS=("data/letters" "data/books/sections" "data/books/original" "data/books/english")

if [ $# -eq 0 ]; then
    echo "Usage: $0 <filename>"
    echo ""
    echo "Example:"
    echo "  $0 \"1327 may 4.md\""
    echo "  $0 \"bauer_1872.md\""
    echo "  $0 \"1349 september 2 ehrenfels\""
    echo ""
    exit 1
fi

FILENAME="$1"

# Remove .md extension if not provided
if [[ ! "$FILENAME" =~ \.md$ ]]; then
    FILENAME="${FILENAME}.md"
fi

echo "========================================"
echo "Document Fact Extraction Workflow"
echo "========================================"
echo ""

# Search for the file in multiple directories
DOCUMENT_PATH=""
for dir in "${SEARCH_DIRS[@]}"; do
    if [ -f "$dir/$FILENAME" ]; then
        DOCUMENT_PATH="$dir/$FILENAME"
        break
    fi
done

# Verify the document file exists
if [ -z "$DOCUMENT_PATH" ]; then
    echo "ERROR: Document file not found: $FILENAME"
    echo ""
    echo "Searched in:"
    for dir in "${SEARCH_DIRS[@]}"; do
        echo "  - $dir/"
    done
    echo ""
    echo "Looking for similar files..."
    # Try to find similar filenames across all search directories
    for dir in "${SEARCH_DIRS[@]}"; do
        find "$dir" -type f -name "*${FILENAME%.md}*" 2>/dev/null | head -3
    done
    exit 1
fi

# Extract date from filename
FILENAME_BASE="${FILENAME%.md}"
DATE=$("$SCRIPT_DIR/convert_date_to_iso.sh" "$FILENAME_BASE")

if [ -z "$DATE" ]; then
    echo "WARNING: Could not parse date from filename: $FILENAME"
    DATE="unknown"
fi

# Extract source from document file
SOURCE=$("$SCRIPT_DIR/extract_letter_source.sh" "$DOCUMENT_PATH")

if [ -z "$SOURCE" ]; then
    echo "WARNING: Could not extract source from document file"
    SOURCE="(source not found in file)"
fi

echo "----------------------------------------"
echo "Document to process:"
echo "  Date: $DATE"
echo "  File: $FILENAME"
echo "  Path: $DOCUMENT_PATH"
echo "  Source: $SOURCE"
echo "----------------------------------------"
echo ""

# Step 2: Trigger agent workflow
echo "=========================================="
echo "CLAUDE CODE WORKFLOW TRIGGER"
echo "=========================================="
echo ""
echo "This is where Claude Code should:"
echo ""
echo "1. Launch fact-extractor agent"
echo "   - Input: $DOCUMENT_PATH"
echo "   - Output: /tmp/facts_extract_${FILENAME%.md}.json (temp file)"
echo ""
echo "2. Optionally: fact-source-verifier agent"
echo "   - Input: /tmp/facts_extract_${FILENAME%.md}.json"
echo "   - Verify extracted facts against source document"
echo "   - Updates temp file to remove unsupported facts"
echo ""
echo "3. Optionally: fact-irrelevant-verifier agent"
echo "   - Input: /tmp/facts_extract_${FILENAME%.md}.json"
echo "   - Check if facts meet genealogical relevance criteria"
echo "   - Updates temp file to remove irrelevant facts"
echo ""
echo "4. Merge temporary facts into data/facts.json"
echo "   - Command: python3 scripts/merge_facts.py /tmp/facts_extract_${FILENAME%.md}.json"
echo "   - This merges, validates, and sorts chronologically"
echo ""
echo "5. Launch fact-syntax-verifier agent"
echo "   - Verify: data/facts.json structure and sorting after merge"
echo ""
echo "=========================================="
echo ""

exit 0
