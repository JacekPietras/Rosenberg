# Rosenberg Research Process Architecture

## Google Docs Integration
- **setup.sh**: Interactive OAuth 2.0 token configuration for Google Docs access
- **download_doc.sh**: Downloads documents from Google Docs knowledge base using Drive API
- **token.txt**: OAuth token file (created by setup.sh)

## Document Processing Pipeline
- **process_document.sh**: Main workflow orchestrating download, clean, split operations
- **clean_markdown.sh**: Removes image references and base64 data from markdown
- **split_by_h1.sh**: Splits documents by H1 headings into section files
- **split_by_h3.sh**: Splits letters by H3 headings into individual dated files

## Language Extraction
- **extract_languages.sh**: Extracts bilingual content (German/English) from documents

## Data Management
- **facts_verify_json.sh**: Validates JSON structure and chronological ordering
- **sort_facts_by_date.py**: Sorts facts.json chronologically
- **merge_facts.py**: Merges new facts into facts.json with automatic sorting
- **print_facts_by_date.sh**: Prints facts matching a specific date
- **remove_facts_by_date.sh**: Removes facts matching a specific date

## Data Validation & Reporting
- **compare_dates.sh**: Generates comparison reports between facts.json and letter files
- **print_fact_dates.sh**: Extracts dates from facts.json
- **print_letter_dates.sh**: Extracts dates from letter filenames
- **convert_date_to_iso.sh**: Converts letter dates to ISO format

## Special Character Cleaning
- **clean_special_chars.sh**: Removes escaped punctuation and special formatting

## Automated Workflows
- **process_next_letter.sh**: Automates processing of next unprocessed letter
- **get_next_letter.sh**: Gets information about next letter to process
- **remove_letter_from_report.sh**: Removes processed letters from report

## Research Process Responsibilities

### Data Acquisition
- setup.sh, download_doc.sh

### Data Processing
- process_document.sh, clean_markdown.sh, split_by_h1.sh, split_by_h3.sh

### Content Extraction
- extract_languages.sh

### Data Management
- facts_verify_json.sh, sort_facts_by_date.py, merge_facts.py, print_facts_by_date.sh, remove_facts_by_date.sh

### Quality Control
- compare_dates.sh, print_fact_dates.sh, print_letter_dates.sh, convert_date_to_iso.sh

### Specialized Cleaning
- clean_special_chars.sh

### Automation
- process_next_letter.sh, get_next_letter.sh, remove_letter_from_report.sh