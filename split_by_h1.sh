#!/bin/bash

# Script to split a markdown file by H1 titles into separate files
# and replace content in original file with links

# Check if filename is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <markdown_file>"
    echo "Example: $0 rosenberg.md"
    exit 1
fi

INPUT_FILE="$1"

# Check if input file exists
if [ ! -f "$INPUT_FILE" ]; then
    echo "Error: File '$INPUT_FILE' not found!"
    exit 1
fi

# Get the base name without extension for creating subdirectory
BASE_NAME=$(basename "$INPUT_FILE" .md)
OUTPUT_DIR="${BASE_NAME}"

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo "Splitting '$INPUT_FILE' by H1 titles..."
echo "Output directory: $OUTPUT_DIR"

# Create backup of original file
cp "$INPUT_FILE" "${INPUT_FILE}.backup"
echo "Backup created: ${INPUT_FILE}.backup"

# Initialize variables
current_section=""
current_file=""
section_count=0
temp_original="${INPUT_FILE}.temp"

# Start building the new original file content
echo "# $BASE_NAME" > "$temp_original"
echo "" >> "$temp_original"

# Read the file line by line
while IFS= read -r line; do
    # Check if line is an H1 title (starts with # but not ##)
    if [[ "$line" =~ ^#[^#] ]]; then
        # Close previous section file if it exists
        if [ -n "$current_file" ]; then
            echo "Created: $current_file"
        fi
        
        # Extract the title (remove the # and leading/trailing spaces)
        title=$(echo "$line" | sed 's/^#[[:space:]]*//' | sed 's/[[:space:]]*$//')
        
        # Create a safe filename from the title
        # Remove special characters and replace spaces with underscores
        safe_title=$(echo "$title" | sed 's/[^a-zA-Z0-9 ]//g' | sed 's/[[:space:]]/_/g' | tr '[:upper:]' '[:lower:]')
        
        # Ensure filename is not empty
        if [ -z "$safe_title" ]; then
            section_count=$((section_count + 1))
            safe_title="section_$section_count"
        fi
        
        current_file="$OUTPUT_DIR/${safe_title}.md"
        
        # Start new section file with the H1 title
        echo "$line" > "$current_file"
        
        # Add link to the new original file
        echo "## [$title](./$OUTPUT_DIR/${safe_title}.md)" >> "$temp_original"
        echo "" >> "$temp_original"
        
    else
        # Add content to current section file
        if [ -n "$current_file" ]; then
            echo "$line" >> "$current_file"
        else
            # This is content before the first H1, add it to the original
            echo "$line" >> "$temp_original"
        fi
    fi
done < "$INPUT_FILE"

# Close the last section file
if [ -n "$current_file" ]; then
    echo "Created: $current_file"
fi

# Replace the original file with the new version containing links
mv "$temp_original" "$INPUT_FILE"

echo ""
echo "✅ Splitting complete!"
echo "📁 Section files created in: $OUTPUT_DIR/"
echo "📝 Original file updated with links to sections"
echo "💾 Backup saved as: ${INPUT_FILE}.backup"
echo ""
echo "Section files created:"
find "$OUTPUT_DIR" -name "*.md" | sort
