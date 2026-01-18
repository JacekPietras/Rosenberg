#!/bin/bash
set -e

# Main workflow to extract and validate facts from the next letter in the report
# This script coordinates the entire process:
# 1. Check/generate report
# 2. Get next letter info
# 3. Trigger Claude Code to run extraction/validation agents
# 4. Remove processed letter from report
#
# Usage: ./scripts/process_next_letter.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPORT_FILE="reports/dates_only_in_letters.md"

echo "========================================"
echo "Letter Fact Extraction Workflow"
echo "========================================"
echo ""

# Step 1: Check if report exists, generate if needed
if [ ! -f "$REPORT_FILE" ]; then
    echo "Report file not found. Generating report..."
    "$SCRIPT_DIR/compare_dates.sh"
    echo ""
    echo "✓ Report generated at: $REPORT_FILE"
    echo ""
    echo "Re-run this script to process the first letter."
    exit 0
fi

# Step 2: Get next letter information
echo "Checking for next letter to process..."
LETTER_INFO=$("$SCRIPT_DIR/get_next_letter.sh")
STATUS=$?

if [ $STATUS -eq 1 ]; then
    if echo "$LETTER_INFO" | grep -q "NO_LETTERS"; then
        echo "✓ All letters have been processed!"
        exit 0
    else
        echo "ERROR: Failed to read report"
        exit 1
    fi
fi

# Parse letter information
eval "$LETTER_INFO"

echo ""
echo "----------------------------------------"
echo "Next letter to process:"
echo "  Date: $DATE"
echo "  File: $FILENAME"
echo "  Path: $PATH"
echo "  Source: $SOURCE"
echo "----------------------------------------"
echo ""

# Verify the letter file exists
if [ ! -f "$PATH" ]; then
    echo "ERROR: Letter file not found: $PATH"
    echo "This entry will be removed from the report."
    "$SCRIPT_DIR/remove_letter_from_report.sh" "$FILENAME"
    echo ""
    echo "Run this script again to process the next letter."
    exit 1
fi

# Step 3: Trigger agent workflow
echo "=========================================="
echo "CLAUDE CODE WORKFLOW TRIGGER"
echo "=========================================="
echo ""
echo "This is where Claude Code should:"
echo ""
echo "1. Launch fact-extractor agent"
echo "   - Input: $PATH"
echo "   - Prompt: prompts/prompt.txt"
echo "   - Output: Append to data/facts.json"
echo ""
echo "2. Launch fact-syntax-verifier agent"
echo "   - Verify: data/facts.json structure and sorting"
echo ""
echo "3. Optionally: fact-source-verifier agent"
echo "   - Verify extracted facts against source"
echo ""
echo "4. Optionally: fact-irrelevant-verifier agent"
echo "   - Check if facts meet genealogical relevance criteria"
echo ""
echo "=========================================="
echo ""
echo "If you are running this script directly (not through Claude Code),"
echo "the workflow is paused here. Claude Code will handle the agent"
echo "orchestration and then complete the workflow."
echo ""
echo "After agents complete successfully, run:"
echo "  ./scripts/remove_letter_from_report.sh \"$FILENAME\""
echo ""
echo "To manually complete the workflow."
echo ""

# Note: When run by Claude Code, the agents will be invoked here
# and the script will continue to the cleanup step

# Step 4: Cleanup (only reached if agents succeeded)
# This will be called separately or by Claude Code after agents complete
# "$SCRIPT_DIR/remove_letter_from_report.sh" "$FILENAME"

exit 0
