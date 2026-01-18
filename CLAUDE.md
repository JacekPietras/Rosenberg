# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A historical research tool for processing, organizing, and analyzing medieval German genealogical
documents about the von Rosenberg family (13th-16th centuries).

**Primary Knowledge Base**: Historical sources are maintained in Google Docs, which serves as the
authoritative repository where research documents are created, edited, and updated. The OAuth
integration provides read access to this cloud-based knowledge base.

The system downloads documents from Google Docs, converts them to markdown, extracts bilingual
content (German/English), and maintains a structured JSON database of historical facts with dates,
sources, and relationships in the local repository.

## Core Workflow Commands

### OAuth Token Setup
```bash
./scripts/setup.sh
```
Interactive script that guides through OAuth 2.0 token configuration to access the Google Docs
knowledge base where historical sources are maintained. Token saved to `scripts/token.txt` and
provides readonly access to the source documents.

### Process Google Documents
```bash
./scripts/process_document.sh <GOOGLE_DOC_URL> [OUTPUT_NAME]
```
Main workflow: syncs document from the Google Docs knowledge base, cleans markdown, splits by
H1 sections into `data/books/sections/`. Use this to pull updated source documents from the cloud
repository into the local working directory.

### Extract Language-Specific Content
```bash
./scripts/extract_languages.sh [filename.md]
```
Processes bilingual tables in `data/books/sections/`:
- Left column (original German) → `data/books/original/`
- Right column (English) → `data/books/english/`

### Clean Special Characters
```bash
./scripts/clean_special_chars.sh [directory]
```
Removes escaped punctuation (`\. ` → `. `, `\*` → `*`) from markdown files to improve readability.

### Split Documents by H1 or H3
```bash
./scripts/split_by_h1.sh <input_file>
./scripts/split_by_h3.sh <input_file>
```
Creates individual section files and updates main document with links.

### Sort Facts Database
```bash
python3 scripts/sort_facts_by_date.py
```
Sorts `data/facts.json` chronologically to prevent AI hallucinations when processing genealogical data.

## Data Architecture

### Directory Structure
```
data/
├── books/             # Source books from knowledge base
│   ├── sections/      # Bilingual versions
│   ├── original/      # German-only versions
│   └── english/       # English-only versions
├── documents/original/# Individual historical charters (by date)
├── diagrams/          # Genealogical tree diagrams
├── variations.md      # Name variations and epithets index
└── facts.json         # Structured genealogical database
```

### facts.json Schema
Each entry contains:
- `source`: Archive/document reference
- `date`: ISO 8601 format (YYYY-MM-DD or YYYY)
- `facts`: Array of relationship/event statements

**Critical**: facts.json MUST be kept sorted by date chronologically. Always run `sort_facts_by_date.py` after manual edits.

### Document Naming Convention
Historical charters in `data/documents/original/` use format:
- `YYYY month day [location].md` (e.g., "1327 may 4.md", "1349 september 2 ehrenfels.md")
- Duplicates append `_2`, `_3` etc.

## Historical Context

### Subject Matter
Documents chronicle the von Rosenberg noble family in Franconia/Odenwald region (modern Germany):
- Primary timeframe: 1299-1632
- Key locations: Boxberg, Rosenberg, Uissigheim, Bartenstein
- Related families: von Uissigheim, von Thüngen, von Erligheim

### Genealogical Relationships
Facts capture various relationship types:
- Family: "X is son/daughter/spouse of Y", "X is brother of Y"
- Titles: "X is titled Ritter/Edelknecht/Vogt"
- Transactions: "X sold property to Y", "X served as surety for Y"
- Offices: "X is Vogt zu [location]", "X is Komtur"

### Common German Terms
- **Ritter**: Knight
- **Edelknecht**: Squire/nobleman
- **Vogt**: Bailiff
- **Gülten/Zinse**: Rents/dues
- **Mannlehen**: Male fief
- **Burggut**: Castle property
- **Zehnten**: Tithe

## Working with Bilingual Documents

Source books in `data/books/sections/` use two-column markdown tables:
- Left column: Original German text
- Right column: English translation

The `extract_languages.sh` script:
1. Preserves all non-table content (headings, paragraphs) in both outputs
2. Extracts left column only for German version
3. Extracts right column only for English version
4. Processes both languages simultaneously for efficiency

## Data Integrity Guidelines

1. **Date Consistency**: All dates in facts.json must be sortable (YYYY or YYYY-MM-DD)
2. **Source Citations**: Every fact entry requires valid source reference
3. **Relationship Clarity**: Avoid ambiguous pronouns; use full names
4. **Name Variations**: Consult `data/variations.md` for historical name spellings
5. **No Hallucinations**: When working with historical data, never infer facts not explicitly stated in sources

## Script Implementation Notes

### OAuth Token Security
- Token stored in `scripts/token.txt` (gitignored)
- Provides readonly access to Google Docs knowledge base where historical sources are maintained
- Tokens expire; re-run `setup.sh` if API calls fail
- Uses Google Drive API v3 with readonly scope

### Document Processing Pipeline
1. **Download** (`download_doc.sh`): Fetches via Drive API, saves as markdown
2. **Clean** (`clean_markdown.sh`): Removes image references and base64 data
3. **Split** (`split_by_h1.sh`): Creates section files, updates main doc with links
4. **Extract** (`extract_languages.sh`): Separates bilingual tables

### Error Handling
Scripts use `set -e` for fail-fast behavior. Check:
- OAuth token validity
- File permissions (scripts must be executable)
- Directory existence before file operations

## Python Requirements

The project uses Python 3 for the facts sorting utility. No external dependencies required (uses only standard library: `json`, `datetime`, `sys`, `os`).
