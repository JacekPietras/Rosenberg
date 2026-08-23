# Rosenberg Research Process Architecture

## Overview
The Rosenberg research process is a comprehensive system for transforming historical German genealogical documents into structured facts. It leverages Google Docs as the primary knowledge base, automates document processing workflows, and maintains a structured JSON database of historical relationships.

## System Components

### Google Docs Integration
- **setup.sh**: Interactive OAuth 2.0 token configuration for Google Docs access
- **download_doc.sh**: Downloads documents from Google Docs knowledge base using Drive API
- **token.txt**: OAuth token file (created by setup.sh)

### Document Processing Pipeline
- **process_document.sh**: Main workflow orchestrating download, clean, split operations
- **clean_markdown.sh**: Removes image references and base64 data from markdown
- **split_by_h1.sh**: Splits documents by H1 headings into section files
- **split_by_h3.sh**: Splits letters by H3 headings into individual dated files

### Language Extraction
- **extract_languages.sh**: Extracts bilingual content (German/English) from documents

### Data Management
- **facts_verify_json.sh**: Validates JSON structure and chronological ordering
- **sort_facts_by_date.py**: Sorts facts.json chronologically
- **merge_facts.py**: Merges new facts into facts.json with automatic sorting
- **print_facts_by_date.sh**: Prints facts matching a specific date
- **remove_facts_by_date.sh**: Removes facts matching a specific date

### Data Validation & Reporting
- **compare_dates.sh**: Generates comparison reports between facts.json and letter files
- **print_fact_dates.sh**: Extracts dates from facts.json
- **print_letter_dates.sh**: Extracts dates from letter filenames
- **convert_date_to_iso.sh**: Converts letter dates to ISO format

### Special Character Cleaning
- **clean_special_chars.sh**: Removes escaped punctuation and special formatting

### Automated Workflows
- **process_next_letter.sh**: Automates processing of next unprocessed letter
- **get_next_letter.sh**: Gets information about next letter to process
- **remove_letter_from_report.sh**: Removes processed letters from report

## Data Flow Architecture

### Source to Fact Pipeline
```
Google Docs Source → download_doc.sh → clean_markdown.sh → split_by_h1.sh
                     ↓
              data/books/sections/
                     ↓
              extract_languages.sh
                     ↓
              data/books/original/ ← split_by_h3.sh
                     ↓
              data/letters/
                     ↓
              fact-extractor agent → data/facts.json
                     ↓
              sort_facts_by_date.py
                     ↓
              compare_dates.sh → reports/
```

### Key Data Structures
- **data/books/sections/**: Bilingual documents with German/English columns
- **data/books/original/**: German-only versions of documents
- **data/books/english/**: English-only versions of documents
- **data/letters/**: Individual historical letters split by date
- **data/facts.json**: Structured database of historical facts
- **reports/**: Validation reports showing date comparisons

## Agent Integrations

### Fact Extraction Agents
- **fact-extractor**: Processes individual letters to extract genealogical facts
- **fact-syntax-verifier**: Validates fact extraction syntax and structure
- **fact-source-verifier**: Verifies source citations in extracted facts
- **fact-irrelevant-verifier**: Identifies and filters out irrelevant facts

### Workflow Agents
- **process-next-letter**: Automates the processing of the next unprocessed letter
- **process-document**: Handles specific document processing requests

## Workflow Patterns

### Automated Processing Workflow
1. `/process-next-letter` slash command triggers `process_next_letter.sh`
2. System identifies next unprocessed letter from `reports/dates_only_in_letters.md`
3. Letter details are displayed for agent processing
4. `fact-extractor` agent processes the letter
5. `fact-syntax-verifier` validates the extracted facts
6. Processed letter is removed from the report
7. Progress is reported to the user

### Manual Processing Workflow
1. `/process-document <filename>` slash command triggers `process_document.sh`
2. Document details are displayed for agent processing
3. `fact-extractor` agent processes the letter
4. `fact-source-verifier` and `fact-irrelevant-verifier` validate facts
5. Existing facts for the date are retrieved and merged
6. Old facts are removed and new facts are merged
7. `fact-syntax-verifier` validates the updated facts
8. Progress is reported to the user (no report modification)

## Security & Data Integrity

### OAuth Security
- Token stored in `scripts/token.txt` (gitignored)
- Provides readonly access to Google Docs knowledge base
- Tokens expire; re-run `setup.sh` if API calls fail
- Uses Google Drive API v3 with readonly scope

### Data Validation
- All dates in facts.json must be sortable (YYYY or YYYY-MM-DD)
- Every fact entry requires valid source reference
- Relationship clarity: avoid ambiguous pronouns; use full names
- Name variations: consult `data/variations.md` for historical spellings
- No hallucinations: never infer facts not explicitly stated in sources

## Script Implementation Details

### Error Handling
- Scripts use `set -e` for fail-fast behavior
- Check OAuth token validity
- Check file permissions (scripts must be executable)
- Check directory existence before file operations

### Document Processing Pipeline
1. **Download** (`download_doc.sh`): Fetches via Drive API, saves as markdown
2. **Clean** (`clean_markdown.sh`): Removes image references and base64 data
3. **Split** (`split_by_h1.sh`): Creates section files, updates main doc with links
4. **Extract** (`extract_languages.sh`): Separates bilingual tables

### Data Validation Tools
- `compare_dates.sh`: Cross-references dates, generates reports in `reports/`
- `facts_verify_json.sh`: Validates JSON syntax and chronological ordering
- `convert_date_to_iso.sh`: Handles various date formats including ranges
- Helper scripts: `print_fact_dates.sh`, `print_letter_dates.sh`, `extract_letter_source.sh`