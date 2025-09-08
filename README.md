# Rosenberg Document Processor

A tool for downloading, cleaning, and organizing Google Docs documents into structured markdown files.

## Project Structure

```
Rosenberg/
├── README.md                 # This file
├── scripts/                  # All executable scripts
│   ├── setup.sh              # Interactive setup for OAuth token
│   ├── process_document.sh   # Main workflow script
│   ├── extract_original.sh   # Extract original language content
│   ├── download_doc.sh       # Download Google Docs as markdown
│   ├── clean_markdown.sh     # Clean downloaded markdown
│   ├── split_by_h1.sh        # Split document by H1 sections
│   └── token.txt             # OAuth token (created by setup)
├── data/                     # Processed documents
│   ├── rosenberg.md          # Main processed document
│   ├── sections/             # Individual document sections (bilingual)
│   └── original/            # Original language content only
└── docs/                     # Project documentation
```

## Quick Start

### 1. Setup OAuth Token

Run the interactive setup script:

```bash
./scripts/setup.sh
```

This will guide you through:
- Getting an OAuth 2.0 token from Google
- Saving it securely to `scripts/token.txt`

### 2. Process a Document

Use the main processing script:

```bash
./scripts/process_document.sh https://docs.google.com/document/d/1BAfsC2IshoZsX5ulN1dW2ywa9ePYn45DmyGQeAanw10 rosenberg
```

This will:
1. Download the Google Doc as markdown
2. Clean up image references and formatting
3. Split the document by H1 headings into separate files
4. Create a main document with links to all sections

### 3. Extract Original Language Content (Optional)

If your documents contain bilingual tables (original language in left column, translations in right column), you can extract only the original content:

```bash
./scripts/extract_original.sh
```

Or process a specific file:
```bash
./scripts/extract_original.sh filename.md
```

## Manual Setup (Alternative)

If you prefer to set up the OAuth token manually:

### Get OAuth 2.0 Token

1. Go to the [Google OAuth 2.0 Playground](https://developers.google.com/oauthplayground)
2. In the "Select & authorize APIs" section, find **"Drive API v3"**
3. Expand it and select: `https://www.googleapis.com/auth/drive.readonly`
4. Click **"Authorize APIs"** and sign in with your Google account
5. Click **"Exchange authorization code for tokens"**
6. Copy the **"Access token"** value (starts with `ya29.a0...`)
7. Save it to `scripts/token.txt`:
   ```bash
   echo "your_token_here" > scripts/token.txt
   chmod 600 scripts/token.txt
   ```

## Output Files

After processing, you'll find:

- **`data/[document-name].md`** - Main document with links to sections
- **`data/sections/`** - Directory containing individual section files
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
Downloads a Google Doc as markdown using the Google Drive API.
- Supports both document IDs and full URLs
- Automatically detects output format based on file extension
- Requires valid OAuth token

### `clean_markdown.sh`
Removes image references and base64 data from downloaded markdown files.
- Removes `![](image[N])` references
- Removes `[image[N]]: <data:...>` definitions

### `extract_original.sh`
Extracts original language content from bilingual markdown files.
- Processes files in `data/sections/` directory
- Extracts left column content from tables (original language)
- Preserves all non-table content
- Creates original-only files in `data/original/` directory

### `split_by_h1.sh`
Splits a markdown document by H1 headings into separate files.
- Creates individual files for each H1 section
- Updates main document with links to sections
- Creates backup of original file
