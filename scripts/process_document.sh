#!/bin/bash

# Main script to process Google Docs documents
# This script orchestrates the entire workflow: download, clean, and split documents
#
# Usage: ./process_document.sh <GOOGLE_DOC_URL> [OUTPUT_NAME]
#
# Example:
# ./process_document.sh https://docs.google.com/document/d/1BAfsC2IshoZsX5ulN1dW2ywa9ePYn45DmyGQeAanw10 rosenberg

set -e

# --- Configuration ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DATA_DIR="$PROJECT_ROOT/data"
TOKEN_FILE="$SCRIPT_DIR/token.txt"

# --- Validation ---
if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    echo "Usage: $0 <GOOGLE_DOC_URL> [OUTPUT_NAME]"
    echo ""
    echo "Arguments:"
    echo "  GOOGLE_DOC_URL  - Full URL of the Google Doc to process"
    echo "  OUTPUT_NAME     - Optional name for output files (default: extracted from URL)"
    echo ""
    echo "Example:"
    echo "  $0 https://docs.google.com/document/d/1BAfsC2IshoZsX5ulN1dW2ywa9ePYn45DmyGQeAanw10 rosenberg"
    echo ""
    echo "Prerequisites:"
    echo "  1. OAuth token must be saved in scripts/token.txt"
    echo "  2. All scripts must be executable (run: chmod +x scripts/*.sh)"
    exit 1
fi

DOC_URL="$1"
OUTPUT_NAME="${2:-document}"
OUTPUT_FILE="$DATA_DIR/${OUTPUT_NAME}.md"

# --- Check Prerequisites ---
if [ ! -f "$TOKEN_FILE" ]; then
    echo "❌ Error: OAuth token file not found at $TOKEN_FILE"
    echo ""
    echo "Please follow these steps to get a token:"
    echo "1. Go to https://developers.google.com/oauthplayground"
    echo "2. Select 'Drive API v3' and the scope: https://www.googleapis.com/auth/drive.readonly"
    echo "3. Authorize and get the access token"
    echo "4. Save the token to $TOKEN_FILE"
    exit 1
fi

OAUTH_TOKEN="$(cat "$TOKEN_FILE")"

if [ -z "$OAUTH_TOKEN" ]; then
    echo "❌ Error: OAuth token is empty in $TOKEN_FILE"
    exit 1
fi

# --- Create necessary directories ---
mkdir -p "$DATA_DIR"

echo "🚀 Starting document processing workflow..."
echo "📄 Document URL: $DOC_URL"
echo "📁 Output file: $OUTPUT_FILE"
echo ""

# --- Step 1: Download the document ---
echo "📥 Step 1: Downloading document..."
if ! "$SCRIPT_DIR/download_doc.sh" "$DOC_URL" "$OAUTH_TOKEN" "$OUTPUT_FILE"; then
    echo "❌ Failed to download document"
    exit 1
fi
echo ""

# --- Step 2: Clean the markdown ---
echo "🧹 Step 2: Cleaning markdown..."
if ! "$SCRIPT_DIR/clean_markdown.sh" "$OUTPUT_FILE"; then
    echo "❌ Failed to clean markdown"
    exit 1
fi
echo ""

# --- Step 3: Split by H1 sections ---
echo "✂️  Step 3: Splitting document by H1 sections..."
cd "$SCRIPT_DIR"
if ! "./split_by_h1.sh" "$OUTPUT_FILE"; then
    echo "❌ Failed to split document"
    exit 1
fi
cd "$PROJECT_ROOT"
echo ""

# --- Success ---
echo "✅ Document processing complete!"
echo ""
echo "📁 Files created:"
echo "   Main document: $OUTPUT_FILE"
echo "   Sections: $DATA_DIR/sections/"
echo ""
echo "🔍 To view the processed document:"
echo "   cat $OUTPUT_FILE"
echo ""
echo "📂 To see all section files:"
echo "   ls -la $DATA_DIR/sections/"
