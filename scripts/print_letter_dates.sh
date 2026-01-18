#!/bin/bash

# Print all dates from letter filenames in data/letters/original
# Format: original_filename [YYYY-MM-DD]

# Get the script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Path to letters directory
LETTERS_DIR="$PROJECT_ROOT/data/letters/original"

# Path to conversion script
CONVERT_SCRIPT="$SCRIPT_DIR/convert_date_to_iso.sh"

# Check if directory exists
if [ ! -d "$LETTERS_DIR" ]; then
    echo "Error: $LETTERS_DIR not found"
    exit 1
fi

# Check if conversion script exists
if [ ! -f "$CONVERT_SCRIPT" ]; then
    echo "Error: $CONVERT_SCRIPT not found"
    exit 1
fi

# Make sure conversion script is executable
chmod +x "$CONVERT_SCRIPT"

# List all .md files, extract filenames, and convert to ISO format
find "$LETTERS_DIR" -name "*.md" -type f | \
    sed 's|.*/||' | \
    sed 's|\.md$||' | \
    grep -v '^list$' | \
    sort | \
    while IFS= read -r filename; do
        # Convert to ISO format using the conversion script
        iso_date=$("$CONVERT_SCRIPT" "$filename")

        if [ -n "$iso_date" ]; then
            echo "$filename [$iso_date]"
        else
            echo "$filename"
        fi
    done

