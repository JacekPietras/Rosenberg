#!/bin/bash

# Extract source (Quellen) from a letter file
# Input: path to letter file
# Output: source text (everything after "Quellen: " until the next blank line)

if [ $# -eq 0 ]; then
    echo "Usage: $0 <letter_file>"
    exit 1
fi

LETTER_FILE="$1"

if [ ! -f "$LETTER_FILE" ]; then
    echo "Error: File not found: $LETTER_FILE"
    exit 1
fi

# Extract lines starting from "Quellen:" until the first blank line
# Remove the "Quellen: " prefix and join multiple lines with a space
grep -A 20 "^Quellen:" "$LETTER_FILE" | \
    sed -n '/^Quellen:/,/^$/p' | \
    sed 's/^Quellen: *//' | \
    grep -v '^$' | \
    tr '\n' ' ' | \
    sed 's/  */ /g' | \
    sed 's/ $//'

