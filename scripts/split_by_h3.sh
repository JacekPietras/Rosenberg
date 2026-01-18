#!/bin/bash

# Script to split a markdown file by H3 (###) titles into separate files
# Defaults follow project structure in README.md
# - Input default: ../data/books/original/letters.md
# - Output default: ../data/letters/original/
# The script does NOT modify the original file; it only creates section files.

set -euo pipefail

# Usage
if [[ ${1-} == "-h" || ${1-} == "--help" ]]; then
  echo "Usage: $0 [input_markdown] [output_dir]"
  echo "Defaults: input=../data/books/original/letters.md output=../data/letters/original"
  exit 0
fi

# Resolve paths relative to this script's directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEFAULT_INPUT="${SCRIPT_DIR}/../data/books/original/letters.md"
DEFAULT_OUTPUT="${SCRIPT_DIR}/../data/letters/original"

INPUT_FILE="${1:-$DEFAULT_INPUT}"
OUTPUT_DIR="${2:-$DEFAULT_OUTPUT}"

# Validate input file
if [[ ! -f "$INPUT_FILE" ]]; then
  echo "Error: Input file not found: $INPUT_FILE" >&2
  exit 1
fi

# Prepare output directory
mkdir -p "$OUTPUT_DIR"

echo "Splitting by H3 (###) titles"
echo "Input : $INPUT_FILE"
echo "Output: $OUTPUT_DIR"

current_file=""
created_count=0
section_count=0

# Helper to create a safe, unique filename from a title
make_safe_filename() {
  local title="$1"
  # Strip markdown emphasis markers and surrounding spaces
  title="${title//\*/}"     # remove asterisks
  title="${title//\`/}"     # remove backticks
  title="${title//\[/}"; title="${title//\]/}"
  title="${title//\(/}"; title="${title//\)/}"
  title="${title//\./}"     # remove dots to keep names simple
  title="$(echo "$title" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
  # Keep alnum and spaces -> underscores, lowercase
  local safe
  safe="$(echo "$title" | sed 's/[^a-zA-Z0-9 ]//g' | sed 's/[[:space:]]\+/_/g' | tr '[:upper:]' '[:lower:]')"
  if [[ -z "$safe" ]]; then
    section_count=$((section_count + 1))
    safe="section_${section_count}"
  fi
  # Ensure uniqueness if file exists
  local candidate="$safe"
  local n=1
  while [[ -e "$OUTPUT_DIR/${candidate}.md" ]]; do
    n=$((n + 1))
    candidate="${safe}_${n}"
  done
  echo "$candidate"
}

# Read and split
while IFS= read -r line || [[ -n "$line" ]]; do
  # Detect H3 heading: starts with ###, followed by optional spaces, and NOT another #
  if [[ "$line" =~ ^###[[:space:]]*[^#] ]]; then
    # Close previous section file notice (no need to write here)
    # Extract title text from the H3 (strip leading ### and spaces)
    title="$(echo "$line" | sed 's/^###\s*//')"
    safe_title="$(make_safe_filename "$title")"
    current_file="$OUTPUT_DIR/${safe_title}.md"
    echo "Creating: $current_file"
    printf '%s\n' "$line" > "$current_file"
    created_count=$((created_count + 1))
  else
    # Append to current section if one is open
    if [[ -n "$current_file" ]]; then
      printf '%s\n' "$line" >> "$current_file"
    fi
  fi

done < "$INPUT_FILE"

echo ""
echo "✅ Done. Created $created_count files in: $OUTPUT_DIR"
