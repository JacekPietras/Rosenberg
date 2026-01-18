#!/bin/bash

# Print all dates from letter filenames in data/letters/original with their sources
# Format: YYYY-MM-DD | filename | source

# Get the script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Path to letters directory
LETTERS_DIR="$PROJECT_ROOT/data/letters/original"

# Path to conversion script
CONVERT_SCRIPT="$SCRIPT_DIR/convert_date_to_iso.sh"

# Path to source extraction script
EXTRACT_SOURCE_SCRIPT="$SCRIPT_DIR/extract_letter_source.sh"

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

# Check if source extraction script exists
if [ ! -f "$EXTRACT_SOURCE_SCRIPT" ]; then
    echo "Error: $EXTRACT_SOURCE_SCRIPT not found"
    exit 1
fi

# Make sure scripts are executable
chmod +x "$CONVERT_SCRIPT"
chmod +x "$EXTRACT_SOURCE_SCRIPT"

# List all .md files, extract filenames, convert to ISO format, and get sources
find "$LETTERS_DIR" -name "*.md" -type f | \
    grep -v '/list\.md$' | \
    sort | \
    while IFS= read -r filepath; do
        filename=$(basename "$filepath" .md)

        # Convert to ISO format using the conversion script
        iso_date=$("$CONVERT_SCRIPT" "$filename")

        # Extract source from the letter file
        source=$("$EXTRACT_SOURCE_SCRIPT" "$filepath")

        if [ -n "$iso_date" ]; then
            if [ -n "$source" ]; then
                echo "$iso_date | $filename | $source"
            else
                echo "$iso_date | $filename | [No source found]"
            fi
        fi
    done

