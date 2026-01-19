# Process Letter

Extract genealogical facts from a specific document file.

## Usage

This command accepts a document filename as an argument:

```
/process-document <filename>
```

Examples:
- `/process-document "1327 may 4.md"`
- `/process-document "bauer 5.md"`
- `/process-document "1327 may 4"` (the .md extension is optional)

## Workflow Steps

Execute the workflow script with the specified filename:

```bash
./scripts/process_document.sh "$1"
```

Then follow these steps:

1. **Read the script output** to extract:
   - Document path
   - Document filename
   - Date
   - Source citation

2. **Launch fact-extractor agent** with the Task tool:
   - subagent_type: "fact-extractor"
   - prompt: "Extract genealogical facts from the document file: [PATH]\n\nSource reference: [SOURCE]\nDate: [DATE]\n\nRead the document, extract all genealogical facts about the von Rosenberg family and related families"
   - The agent will create `/tmp/facts_extract_[FILENAME].json` and report the path

3. **Launch data verification agents** (IMPORTANT: specify the temp file path):
    - fact-source-verifier:
        - prompt: "Verify the facts in /tmp/facts_extract_[FILENAME].json against their source document"
    - fact-irrelevant-verifier:
        - prompt: "Clean /tmp/facts_extract_[FILENAME].json by removing facts irrelevant to the Rosenberg lineage"
    - These agents will read and update the temp file before merging

4. **Download current facts for that date**:
    - use script print_facts_by_date.sh with the date from step 1
    - merge those facts into the temp file
    - review for duplicates or conflicts

5. **Remove current facts with that date**:
    - use script remove_facts_by_date.sh with the date from step 1

6. **Merge temporary facts into facts.json**:
   ```bash
   python3 scripts/merge_facts.py /tmp/facts_extract_[FILENAME].json
   ```
    - Replace [FILENAME] with the base name from step 1 (e.g., "1327 may 4")
    - This merges the temp file, sorts chronologically, and validates structure

7. **Launch fact-syntax-verifier agent** (optional but recommended):
   - subagent_type: "fact-syntax-verifier"
   - prompt: "Verify the JSON structure, chronological sorting, and quality of data/facts.json after the recent update."

8. **Report results** to user:
   - Validation status
   - Any errors or warnings

## Important Notes

- The .md extension is optional and will be added automatically if not provided
- If the file doesn't exist, the script will suggest similar filenames
- Facts are automatically merged and sorted chronologically
