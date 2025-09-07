#!/bin/bash

# Setup script for the Rosenberg document processing project
# This script helps users set up the OAuth token and verify the environment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOKEN_FILE="$SCRIPT_DIR/token.txt"

echo "🔧 Rosenberg Document Processor Setup"
echo "======================================"
echo ""

# Check if token already exists
if [ -f "$TOKEN_FILE" ]; then
    echo "✅ OAuth token file already exists at: $TOKEN_FILE"
    echo ""
    read -p "Do you want to replace it with a new token? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Setup cancelled. Using existing token."
        exit 0
    fi
fi

echo "📋 To get an OAuth token, follow these steps:"
echo ""
echo "1. Go to the Google OAuth 2.0 Playground:"
echo "   https://developers.google.com/oauthplayground"
echo ""
echo "2. In the 'Select & authorize APIs' section:"
echo "   - Find 'Drive API v3'"
echo "   - Expand it and select: https://www.googleapis.com/auth/drive.readonly"
echo ""
echo "3. Click 'Authorize APIs' and sign in with your Google account"
echo ""
echo "4. Click 'Exchange authorization code for tokens'"
echo ""
echo "5. Copy the 'Access token' value (starts with ya29.a0...)"
echo ""

read -p "Press Enter when you have your OAuth token ready..."
echo ""

echo "Please paste your OAuth token:"
read -r OAUTH_TOKEN

if [ -z "$OAUTH_TOKEN" ]; then
    echo "❌ Error: No token provided"
    exit 1
fi

# Validate token format (basic check)
if [[ ! $OAUTH_TOKEN =~ ^ya29\. ]]; then
    echo "⚠️  Warning: Token doesn't start with 'ya29.' - this might not be a valid OAuth token"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Setup cancelled."
        exit 1
    fi
fi

# Save token to file
echo "$OAUTH_TOKEN" > "$TOKEN_FILE"
chmod 600 "$TOKEN_FILE"  # Restrict permissions for security

echo ""
echo "✅ OAuth token saved to: $TOKEN_FILE"
echo "🔒 File permissions set to 600 (owner read/write only)"
echo ""
echo "🚀 Setup complete! You can now use the document processor:"
echo "   ./scripts/process_document.sh <GOOGLE_DOC_URL> [OUTPUT_NAME]"
echo ""
echo "📖 Example:"
echo "   ./scripts/process_document.sh https://docs.google.com/document/d/1BAfsC2IshoZsX5ulN1dW2ywa9ePYn45DmyGQeAanw10 rosenberg"
