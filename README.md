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
├── README.md                    # This file
├── data/                        # Processed documents
│   ├── books/                   # Source books from knowledge base
│   │   ├── sections/            # Bilingual versions
│   │   ├── original/            # German-only versions
│   │   └── english/             # English-only versions
│   ├── letters/                 # Individual historical letters extracted from books/original/letters.md
│   ├── diagrams/                # Genealogical diagrams extracted from books
│   ├── variations.md            # List of name variations and epithets
│   └── facts.json               # Extracted facts in JSON format
├── reports/                     # Generated comparison reports
│   ├── dates_in_both.md         # Dates in both facts and letters
│   ├── dates_only_in_facts.md   # Dates only in facts.json
│   └── dates_only_in_letters.md # Dates only in letter files
├── sync_from_google/            # Scripts + architecture for syncing docs from Google Docs
│   ├── architecture.md          # Description of the download/sync pipeline
│   ├── setup.sh                 # Interactive setup for OAuth token
│   ├── download_doc.sh          # Download Google Docs as markdown
│   ├── clean_markdown.sh        # Clean downloaded markdown
│   ├── split_by_h1.sh           # Split document by H1 sections
│   ├── extract_languages.sh     # Extract original and English content
│   ├── clean_special_chars.sh   # Clean unnecessary special characters
│   ├── split_by_h3.sh           # Split letters by H3 sections (handles date ranges)
│   └── token.txt                # OAuth token (created by setup)
└── scripts/                     # Fact-extraction workflow scripts
    ├── process_document.sh      # Main workflow script
    ├── sort_facts_by_date.py    # Sort facts.json chronologically
    ├── compare_dates.sh         # Generate 3 comparison files
    ├── print_fact_dates.sh      # Extract dates from facts.json
    ├── print_letter_dates.sh    # Extract dates from letter filenames
    ├── print_facts_by_date.sh   # Print facts matching a specific date
    ├── remove_facts_by_date.sh  # Remove facts matching a specific date
    ├── convert_date_to_iso.sh   # Convert letter dates to ISO (handles ranges)
    ├── extract_letter_source.sh # Extract Quellen from letter files
    ├── parse_letters.py          # Convert letter markdown files to JSON
    ├── add_english_translations.py # Add English text to letter JSON files
    └── parse_books.py             # Combine German and English books into JSON
```

## Quick Start

### 1. Setup OAuth Token

Run the interactive setup script:

```bash
./sync_from_google/setup.sh
```

This will guide you through:
- Getting an OAuth 2.0 token from Google to access the Google Docs knowledge base
- Saving it securely to `sync_from_google/token.txt`
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
./sync_from_google/extract_languages.sh
```

Or process a specific file:
```bash
./sync_from_google/extract_languages.sh filename.md
```

This creates two sets of files:
- `data/books/original/` - Original language content only
- `data/books/english/` - English content only

### 4. Clean Special Characters (Optional)

To improve readability by removing unnecessary escape characters and special formatting:

```bash
./sync_from_google/clean_special_chars.sh
```

Or clean specific directories:
```bash
./sync_from_google/clean_special_chars.sh data/books/original
./sync_from_google/clean_special_chars.sh data/books/english
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
7. Save it to `sync_from_google/token.txt`:
   ```bash
   echo "your_token_here" > sync_from_google/token.txt
   chmod 600 sync_from_google/token.txt
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

### `split_by_h3.sh`
Splits a markdown document by H3 (###) headings into separate files.
- Default input: `data/books/original/letters.md`
- Default output: `data/letters/`
- Creates individual files for each H3 section (typically individual letters)
- Does NOT modify the original file; only creates section files
- Handles date ranges (e.g., "October 23/26") by converting to space-separated format
- Useful for splitting a compiled document of letters into individual dated files

### `sort_facts_by_date.py`
Python utility to sort the facts.json database chronologically.
- Reads `data/facts.json` and sorts all entries by date
- Ensures chronological order to prevent AI hallucinations
- Uses ISO 8601 date format (YYYY-MM-DD or YYYY)
- Should be run after manual edits to facts.json
- No external dependencies (uses standard library only)

### `compare_dates.sh`
Generates three separate comparison files between dates in `facts.json` and letter files.
- Compares dates from `data/facts.json` with dates from `data/letters/` filenames
- Extracts and compares document sources (Quellen) from both facts and letters
- Creates 3 separate markdown files:
  - **`dates_in_both.md`**: Shows matching dates with facts source and letter source side-by-side
  - **`dates_only_in_facts.md`**: Lists dates in facts.json without corresponding letter files
  - **`dates_only_in_letters.md`**: Lists letter files not yet processed into facts.json
- Helps identify discrepancies, missing letters, and unprocessed documents
- Uses `print_fact_dates.sh`, `print_letter_dates.sh`, and `convert_date_to_iso.sh` helper scripts

### `parse_letters.py`
Converts each Markdown file in `data/letters/` into a same-named JSON file in
`data/letters_json/`:

```bash
python3 scripts/parse_letters.py
```

Each JSON file contains the heading date and an ordered `entries` array. Every
entry contains one `sources` string and its `german` text; repeated `Quellen:`
blocks remain separate. English translations can be added later alongside the
`german` field without changing the parser’s data model. To inspect one file
without writing output:

```bash
python3 scripts/parse_letters.py --file "data/letters/1409 april 14.md"
```

### `convert_date_to_iso.sh`
Converts letter filename dates to ISO 8601 format (YYYY-MM-DD or YYYY).
- Handles various date formats: "1327 may 4", "1330", "1360 october 23 26"
- For date ranges (e.g., "october 23 26"), uses the **last** day number (26)
- Supports multiple month name formats (German, English, abbreviations)
- Used by `compare_dates.sh` and `print_letter_dates.sh`

### `add_english_translations.py`
Matches sections in `data/books/english/letters.md` to the German letter JSON
files by normalized date and source, then adds an `english` field to each
matching entry:

```bash
python3 scripts/add_english_translations.py
```

Use `--dry-run` to validate all matches without changing files. Four historical
sections have translated descriptions where the German entry has no matching
archive source; these are matched to their date's sole entry and reported as
warnings.

### `parse_books.py`
Combines matching files from `data/books/german/` and `data/books/english/`
into one JSON file per book under `data/books/json/`:

```bash
python3 scripts/parse_books.py
```

The H1 heading becomes `book`; each H2 section becomes an entry with `title`,
`german`, and `english` fields. The script validates that book and section
titles match before writing output.

### `print_facts_by_date.sh`
Prints facts from facts.json that match a specific date.
- Usage: `./scripts/print_facts_by_date.sh YYYY-MM-DD` or `./scripts/print_facts_by_date.sh YYYY`
- Returns JSON array of all facts matching the specified date
- Example: `./scripts/print_facts_by_date.sh 1327-05-04`
- Example: `./scripts/print_facts_by_date.sh 1327`

### `remove_facts_by_date.sh`
Removes facts from facts.json that match a specific date.
- Usage: `./scripts/remove_facts_by_date.sh YYYY-MM-DD` or `./scripts/remove_facts_by_date.sh YYYY`
- Creates automatic backup before removal (with timestamp)
- Shows facts to be removed before deletion
- Reports count of removed facts
- Example: `./scripts/remove_facts_by_date.sh 1327-05-04`
- Example: `./scripts/remove_facts_by_date.sh 1327`
