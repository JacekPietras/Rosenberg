#!/bin/bash

# Script to clean unnecessary special characters from markdown files
# This script simplifies various special characters that can make text harder to read
#
# Usage: ./clean_special_chars.sh [directory_path]
#
# Examples:
# ./clean_special_chars.sh data/original    # Clean all .md files in data/original/
# ./clean_special_chars.sh data/english     # Clean all .md files in data/english/
# ./clean_special_chars.sh                  # Clean all .md files in data/original/ and data/english/

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Function to clean a single file
clean_file() {
    local file="$1"
    local temp_file="${file}.tmp"
    
    echo "Cleaning: $(basename "$file")"
    
    # Apply precise sed replacements to clean specific problematic patterns
    sed \
        -e 's/\\[.] /. /g' \
        -e 's/\\[.],/, /g' \
        -e 's/\\[.]$/./g' \
        -e 's/\\[*]/*/g' \
        -e 's/\\)/)/g' \
        -e 's/\\(/(/g' \
        -e 's/\\]/]/g' \
        -e 's/\\\[/[/g' \
        "$file" > "$temp_file"
    
    # Move temp file to replace original
    mv "$temp_file" "$file"
    echo "Cleaned: $(basename "$file")"
}

# Function to process all .md files in a directory
process_directory() {
    local dir="$1"
    
    if [ ! -d "$dir" ]; then
        echo "⚠️  Directory not found: $dir"
        return 1
    fi
    
    local file_count=0
    for file in "$dir"/*.md; do
        if [ -f "$file" ]; then
            clean_file "$file"
            file_count=$((file_count + 1))
        fi
    done
    
    if [ $file_count -eq 0 ]; then
        echo "⚠️  No .md files found in $dir"
        return 1
    fi
    
    echo "Processed $file_count files in $dir"
}

# Main execution
if [ "$#" -eq 1 ]; then
    # Process specific directory
    process_directory "$1"
    
elif [ "$#" -eq 0 ]; then
    # Process both default directories
    echo "🧹 Cleaning special characters from markdown files..."
    echo ""
    
    original_dir="$PROJECT_ROOT/data/original"
    english_dir="$PROJECT_ROOT/data/english"
    
    if [ -d "$original_dir" ]; then
        echo "Processing original files:"
        process_directory "$original_dir"
        echo ""
    fi
    
    if [ -d "$english_dir" ]; then
        echo "Processing English files:"
        process_directory "$english_dir"
        echo ""
    fi
    
else
    echo "Usage: $0 [directory_path]"
    echo ""
    echo "Examples:"
    echo "  $0 data/original    # Clean all .md files in data/original/"
    echo "  $0 data/english     # Clean all .md files in data/english/"
    echo "  $0                  # Clean all .md files in both directories"
    exit 1
fi

echo "✅ Special character cleanup complete!"
