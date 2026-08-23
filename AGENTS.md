## Project Overview

See [README.md](README.md) for the project overview, directory structure, and human-facing setup
instructions. This file adds LLM agent-specific workflows, domain knowledge, and
data-integrity guardrails not covered there.

## Core Workflow Commands

### Merge New Facts
```bash
python3 scripts/merge_facts.py <temp_facts_file>
```
Merges a temporary JSON file containing new facts into `data/facts.json`, then automatically sorts chronologically. Used by the fact-extractor agent to append facts without reading the entire database.

### Validate Data Integrity
```bash
./scripts/facts_verify_json.sh    # Validate JSON structure and chronological order
./scripts/compare_dates.sh         # Generate comparison reports in reports/
```
Cross-references dates between facts.json and letter files to identify unprocessed documents and inconsistencies.

### Automated Letter Processing Workflow

**Slash Command:**
```
/process-next-letter
```
Runs the automated workflow for extracting and validating facts from the next unprocessed letter.

**Direct Script:**
```bash
./scripts/process_next_letter.sh
```

**How it works:**
1. Checks if `reports/dates_only_in_letters.md` exists (runs `compare_dates.sh` if not)
2. Identifies the next unprocessed letter from the report
3. Displays letter information for LLM agent processing
4. After agents complete, removes processed letter from report

**Helper Scripts:**
```bash
./scripts/get_next_letter.sh              # Get info about next letter
./scripts/remove_letter_from_report.sh    # Remove processed letter from report
```

**LLM Agent Flow:**
When `/process-next-letter` is invoked, LLM should:
1. Run `process_next_letter.sh` to get letter details
2. Launch `fact-extractor` agent with the letter file
3. Launch `fact-syntax-verifier` agent to validate updates
4. Call `remove_letter_from_report.sh` after successful completion
5. Report progress to user

### Process Specific Document

**Slash Command:**
```
/process-document <filename>
```
Extracts facts from a specific document file by filename. Designed for reprocessing documents with existing facts.

**Direct Script:**
```bash
./scripts/process_document.sh <filename>
```

**Usage Examples:**
```bash
./scripts/process_document.sh "1327 may 4.md"
./scripts/process_document.sh "bauer 5.md"
./scripts/process_document.sh "1349 september 2 ehrenfels"
```

**How it works:**
1. Accepts a document filename as parameter (relative to `data/letters/`)
2. The .md extension is optional and will be added automatically
3. Extracts date and source information from the file
4. Displays document information for LLM agent processing
5. Does NOT modify the dates_only_in_letters.md report (use this for reprocessing)

**When to use:**
- Reprocess a document that was previously extracted
- Extract facts from a specific document regardless of report status
- Update existing facts for a date with improved extraction
- Manual fact extraction workflow outside of the automated queue

**LLM Agent Flow:**
When `/process-document <filename>` is invoked, LLM should:
1. Run `process_document.sh <filename>` to get document details
2. Launch `fact-extractor` agent with the document file
3. Launch `fact-source-verifier` and `fact-irrelevant-verifier` agents
4. Retrieve existing facts for the date using `print_facts_by_date.sh`
5. Manually merge existing and new facts (removing duplicates, resolving conflicts)
6. Remove old facts using `remove_facts_by_date.sh`
7. Merge updated facts using `merge_facts.py`
8. Launch `fact-syntax-verifier` agent to validate updates
9. Report progress to user (including merge decisions and conflict resolutions)
10. Do NOT remove from report (this is for manual/reprocessing use)

## Data Architecture

### facts.json Schema
Each entry contains:
- `source`: Archive/document reference
- `date`: ISO 8601 format (YYYY-MM-DD or YYYY)
- `facts`: Array of relationship/event statements

**Critical**: facts.json MUST be kept sorted by date chronologically. Always run `python3 scripts/sort_facts_by_date.py` after manual edits.

### Letter Naming Convention
Historical letters in `data/letters/` use format:
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

## Data Integrity Guidelines

1. **Date Consistency**: All dates in facts.json must be sortable (YYYY or YYYY-MM-DD)
2. **Source Citations**: Every fact entry requires valid source reference
3. **Relationship Clarity**: Avoid ambiguous pronouns; use full names
4. **Name Variations**: Consult `data/variations.md` for historical name spellings
5. **No Hallucinations**: When working with historical data, never infer facts not explicitly stated in sources
