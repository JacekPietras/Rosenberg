#!/bin/bash

# Script to extract original content from bilingual markdown files
# Processes files in data/sections/ and creates original-only versions in data/original/
# 
# Tables with German (left) and English (right) columns are processed to keep only the left column
# Content outside tables is preserved as-is
#
# Usage: ./extract_original.sh [specific_file.md]
#
# Examples:
# ./extract_original.sh                    # Process all files in data/sections/
# ./extract_original.sh wappengruppen_1977.md  # Process specific file

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SECTIONS_DIR="$PROJECT_ROOT/data/sections"
ORIGINAL_DIR="$PROJECT_ROOT/data/original"

# Create output directory
mkdir -p "$ORIGINAL_DIR"

# Function to process a single file
process_file() {
    local input_file="$1"
    local filename=$(basename "$input_file")
    local output_file="$ORIGINAL_DIR/$filename"
    
    echo "Processing: $filename"
    
    # Initialize variables
    local in_table=false
    local table_header_seen=false
    local temp_file="${output_file}.tmp"
    
    # Clear temp file
    > "$temp_file"
    
    while IFS= read -r line; do
        # Check if we're entering a table (line with | ... | ... |)
        if [[ "$line" =~ ^\|.*\|.*\|$ ]] && [[ ! "$line" =~ ^\|[[:space:]]*:?-+:?[[:space:]]*\|[[:space:]]*:?-+:?[[:space:]]*\|$ ]]; then
            if [[ "$in_table" == false ]]; then
                in_table=true
                table_header_seen=false
            fi
            
            # Extract left column content (everything between first | and second |)
            if [[ "$line" =~ ^\|([^|]*)\|([^|]*)\|$ ]]; then
                left_column="${BASH_REMATCH[1]}"
                # Trim leading and trailing whitespace
                left_column=$(echo "$left_column" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
                # Add the content as a separate paragraph
                echo "$left_column" >> "$temp_file"
                echo "" >> "$temp_file"  # Add blank line for paragraph separation
            fi
            
        # Check for table separator line (| :---- | :---- |)
        elif [[ "$line" =~ ^\|[[:space:]]*:?-+:?[[:space:]]*\|[[:space:]]*:?-+:?[[:space:]]*\|$ ]]; then
            if [[ "$in_table" == true ]]; then
                table_header_seen=true
                # Don't output the separator line
                continue
            fi
            
        # Check if we're exiting a table (empty line or non-table content after table)
        elif [[ "$in_table" == true ]] && [[ ! "$line" =~ ^\|.*\|.*\|$ ]]; then
            in_table=false
            table_header_seen=false
            # Add the current line (it's not part of the table)
            echo "$line" >> "$temp_file"
            
        # Regular content (not in table)
        elif [[ "$in_table" == false ]]; then
            echo "$line" >> "$temp_file"
        fi
        
    done < "$input_file"
    
    # Move temp file to final location
    mv "$temp_file" "$output_file"
    echo "Created: $output_file"
}

# Main execution
if [ "$#" -eq 1 ]; then
    # Process specific file
    specific_file="$SECTIONS_DIR/$1"
    if [ ! -f "$specific_file" ]; then
        echo "❌ Error: File not found: $specific_file"
        exit 1
    fi
    process_file "$specific_file"
    
elif [ "$#" -eq 0 ]; then
    # Process all files in sections directory
    if [ ! -d "$SECTIONS_DIR" ]; then
        echo "❌ Error: Sections directory not found: $SECTIONS_DIR"
        exit 1
    fi
    
    file_count=0
    for file in "$SECTIONS_DIR"/*.md; do
        if [ -f "$file" ]; then
            process_file "$file"
            file_count=$((file_count + 1))
        fi
    done
    
    if [ $file_count -eq 0 ]; then
        echo "⚠️  No .md files found in $SECTIONS_DIR"
        exit 1
    fi
    
else
    echo "Usage: $0 [specific_file.md]"
    echo ""
    echo "Examples:"
    echo "  $0                           # Process all files in data/sections/"
    echo "  $0 wappengruppen_1977.md     # Process specific file"
    exit 1
fi

echo ""
echo "✅ Original content extraction complete!"
echo "📁 Output directory: $ORIGINAL_DIR"
echo ""
echo "📂 Files created:"
find "$ORIGINAL_DIR" -name "*.md" | sort
