#!/bin/bash

# A script to download a Google Doc as a plain text or markdown file using curl.
#
# This method requires a manually obtained OAuth 2.0 Access Token from Google.
# See the accompanying README_manual.md for instructions on how to get one.
#
# Usage: ./download_gdoc_manual.sh <GOOGLE_DOC_ID_OR_URL> <OAUTH_TOKEN> <OUTPUT_FILE>
#
# Example:
# ./download_gdoc_manual.sh 1_aBCd... y29.a0... my_doc.md

set -e

# --- Configuration ---
if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <GOOGLE_DOC_ID_OR_URL> <OAUTH_TOKEN> <OUTPUT_FILE>"
    echo "Please provide the Google Doc ID (or its full URL), a valid OAuth2 token, and an output file path."
    exit 1
fi

DOC_ID_OR_URL="$1"
OAUTH_TOKEN="$2"
OUTPUT_FILE="$3"

# --- ID Extraction ---
# Check if the input is a URL and extract the document ID if it is.
if [[ $DOC_ID_OR_URL == *"/"* ]]; then
    temp_id="${DOC_ID_OR_URL##*/d/}"
    DOC_ID="${temp_id%%/*}"
    echo "Extracted Document ID from URL: ${DOC_ID}"
else
    DOC_ID="$DOC_ID_OR_URL"
    echo "Using provided Document ID: ${DOC_ID}"
fi

# --- Determine Export Format ---
# Get the file extension from the output file name.
FILE_EXTENSION="${OUTPUT_FILE##*.}"
FORMAT=""

if [ "$FILE_EXTENSION" = "md" ]; then
    FORMAT="md"
elif [ "$FILE_EXTENSION" = "txt" ]; then
    FORMAT="txt"
else
    echo "Warning: Unsupported file extension '.${FILE_EXTENSION}'. Defaulting to .txt format for download."
    FORMAT="txt"
fi

# Google Docs export URL.
EXPORT_URL="https://docs.google.com/document/d/${DOC_ID}/export?format=${FORMAT}"

echo "Requesting format: '${FORMAT}' for download."
echo "Downloading Google Doc ID: ${DOC_ID}"
echo "Saving to: ${OUTPUT_FILE}"

# --- Main Logic ---
# Use curl to download the file.
curl --fail -L -H "Authorization: Bearer ${OAUTH_TOKEN}" "${EXPORT_URL}" -o "${OUTPUT_FILE}"

# Check if curl command was successful
if [ $? -eq 0 ]; then
    echo "----------------------------------------"
    echo "✅ Success! Document downloaded as ${OUTPUT_FILE}"
    echo "----------------------------------------"
else
    echo "----------------------------------------"
    echo "❌ Error: Download failed."
    echo "Please check the following:"
    echo "1. The Google Doc ID is correct."
    echo "2. Your OAuth token is valid and has not expired."
    echo "3. You have permission to access the document."
    echo "----------------------------------------"
    exit 1
fi
