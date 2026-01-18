# Rosenberg Document Processor

A tool for syncing historical research documents from Google Docs (the primary knowledge base) and
processing them into structured markdown files for local analysis.

**Source Repository**: Historical documents about the von Rosenberg family are maintained in Google
Docs, which serves as the authoritative cloud-based knowledge base where sources are created,
edited, and updated. This tool provides OAuth integration to pull those documents into a local
working directory.

## Project Structure

```
Rosenberg/
├── README.md                  # This file
├── scripts/                   # All executable scripts
│   ├── setup.sh               # Interactive setup for OAuth token
│   ├── process_document.sh    # Main workflow script
│   ├── extract_languages.sh   # Extract original and English content
│   ├── clean_special_chars.sh # Clean unnecessary special characters
│   ├── download_doc.sh        # Download Google Docs as markdown
│   ├── clean_markdown.sh      # Clean downloaded markdown
│   ├── split_by_h1.sh         # Split document by H1 sections
│   └── token.txt              # OAuth token (created by setup)
└── data/                      # Processed documents
    ├── books/                 # Source books from knowledge base
    │   ├── sections/          # Bilingual versions
    │   ├── original/          # German-only versions
    │   └── english/           # English-only versions
    ├── documents/original/    # Individual historical letters
    ├── diagrams/              # Genealogical diagrams
    ├── variations.md          # List of name variations and epithets
    └── facts.json             # Extracted facts in JSON format
```

## Quick Start

### 1. Setup OAuth Token

Run the interactive setup script:

```bash
./scripts/setup.sh
```

This will guide you through:
- Getting an OAuth 2.0 token from Google to access the Google Docs knowledge base
- Saving it securely to `scripts/token.txt`
- Enabling readonly access to historical source documents maintained in Google Docs

### 2. Process a Document

Use the main processing script to sync a document from the Google Docs knowledge base:

```bash
./scripts/process_document.sh https://docs.google.com/document/d/1BAfsC2IshoZsX5ulN1dW2ywa9ePYn45DmyGQeAanw10 rosenberg
```

This will:
1. Download the document from Google Docs (the source repository) as markdown
2. Clean up image references and formatting
3. Split the document by H1 headings into separate files
4. Create a main document with links to all sections

### 3. Extract Language-Specific Content (Optional)

If your documents contain bilingual tables (original language in left column, English in right column), you can extract both languages simultaneously:

```bash
./scripts/extract_languages.sh
```

Or process a specific file:
```bash
./scripts/extract_languages.sh filename.md
```

This creates two sets of files:
- `data/books/original/` - Original language content only
- `data/books/english/` - English content only

### 4. Clean Special Characters (Optional)

To improve readability by removing unnecessary escape characters and special formatting:

```bash
./scripts/clean_special_chars.sh
```

Or clean specific directories:
```bash
./scripts/clean_special_chars.sh data/books/original
./scripts/clean_special_chars.sh data/books/english
```

## Manual Setup (Alternative)

If you prefer to set up the OAuth token manually to access the Google Docs knowledge base:

### Get OAuth 2.0 Token

1. Go to the [Google OAuth 2.0 Playground](https://developers.google.com/oauthplayground)
2. In the "Select & authorize APIs" section, find **"Drive API v3"**
3. Expand it and select: `https://www.googleapis.com/auth/drive.readonly`
4. Click **"Authorize APIs"** and sign in with your Google account (the one with access to the historical documents)
5. Click **"Exchange authorization code for tokens"**
6. Copy the **"Access token"** value (starts with `ya29.a0...`)
7. Save it to `scripts/token.txt`:
   ```bash
   echo "your_token_here" > scripts/token.txt
   chmod 600 scripts/token.txt
   ```

This token provides readonly access to the Google Docs knowledge base where historical source documents are maintained.

## Output Files

After processing, you'll find:

- **`data/[document-name].md`** - Main document with links to sections
- **`data/books/sections/`** - Directory containing individual section files
- **`data/[document-name].md.backup`** - Backup of the original downloaded file

## Script Details

### `setup.sh`
Interactive setup script that guides you through OAuth token configuration.

### `process_document.sh`
Main workflow script that orchestrates the entire process:
- Downloads the Google Doc
- Cleans the markdown
- Splits into sections
- Provides status updates and error handling

### `download_doc.sh`
Downloads a document from the Google Docs knowledge base as markdown using the Google Drive API.
- Accesses the cloud-based repository where historical sources are maintained
- Supports both document IDs and full URLs
- Automatically detects output format based on file extension
- Requires valid OAuth token for readonly access

### `clean_markdown.sh`
Removes image references and base64 data from downloaded markdown files.
- Removes `![](image[N])` references
- Removes `[image[N]]: <data:...>` definitions

### `extract_languages.sh`
Extracts both original and English content from bilingual markdown files.
- Processes files in `data/books/sections/` directory
- Extracts left column content from tables (original language) → `data/books/original/`
- Extracts right column content from tables (English) → `data/books/english/`
- Preserves all non-table content in both output versions
- Processes both languages simultaneously for efficiency

### `clean_special_chars.sh`
Cleans specific problematic escape sequences from markdown files.
- Fixes escaped sentence endings (`\. ` → `. `)
- Removes escaped punctuation (`\*` → `*`, `\)` → `)`, `\(` → `(`)
- Fixes escaped brackets (`\[` → `[`, `\]` → `]`)
- Targets only the most common problematic patterns
- Precise and focused approach to improve readability

### `split_by_h1.sh`
Splits a markdown document by H1 headings into separate files.
- Creates individual files for each H1 section
- Updates main document with links to sections
- Creates backup of original file
