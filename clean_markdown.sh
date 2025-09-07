#!/bin/bash

# A script to clean markdown files downloaded from Google Docs.
# It removes the image reference tags and the base64 image data definitions.
#
# Usage: ./clean_markdown.sh <path_to_markdown_file>
#
# Example:
# ./clean_markdown.sh my_document.md

set -e

# --- Validation ---
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <MARKDOWN_FILE>"
    echo "Please provide the path to the markdown file you want to clean."
    exit 1
fi

MARKDOWN_FILE="$1"

if [ ! -f "$MARKDOWN_FILE" ]; then
    echo "Error: File not found at '${MARKDOWN_FILE}'"
    exit 1
fi

# Removal of images from text file
sed -i '' \
    -e '/!\[\]\[image[0-9]\{1,\}\]/d' \
    -e '/^\[image[0-9]\{1,\}\]: <.*>$/d' \
    "$MARKDOWN_FILE"

echo "----------------------------------------"
echo "✅ Success! Image references removed from ${MARKDOWN_FILE}"
echo "----------------------------------------"

