# Process Document

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
    - fact-name-normalizer:
        - prompt: "Normalize medieval name and location variations in /tmp/facts_extract_[FILENAME].json using data/variations.md as reference"
    - fact-source-verifier:
        - prompt: "Verify the facts in /tmp/facts_extract_[FILENAME].json against their source document"
    - fact-irrelevant-verifier:
        - prompt: "Clean /tmp/facts_extract_[FILENAME].json by removing facts irrelevant to the Rosenberg lineage"
    - These agents will read and update the temp file before merging

4. **Download current facts for that date**:
    - use script `print_facts_by_date.sh` with the date from step 1
    - **Manual merging by agent**: Read both the existing facts (from print_facts_by_date.sh) and the newly extracted facts (in temp file)
    - **Decision-making**: The agent should decide individually based on the situation:
      - If facts are from the same document: Merge them, removing duplicates and combining complementary information
      - If facts differ (same date, different documents): Keep both sets separately with their respective sources
      - If facts are identical: Keep only one version
    - **Manual review by Claude**: Carefully examine for:
      - Duplicate facts (same information, slightly different wording)
      - Conflicting information (same event, different details)
      - Complementary facts (same event, additional context)
    - Update the temp file with the merged result

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
   - Number of facts from existing database for this date
   - Number of newly extracted facts
   - Merging decision made (duplicates removed, conflicts resolved, etc.)
   - Final count of facts after merge
   - Validation status
   - Any errors or warnings

## Important Notes

- The .md extension is optional and will be added automatically if not provided
- If the file doesn't exist, the script will suggest similar filenames
- Facts are automatically merged and sorted chronologically
- This command is designed for reprocessing documents, allowing you to update existing facts
- Always review existing facts before removal to avoid data loss

## Conflict Resolution Guidelines

When merging facts manually in step 4:

1. **Same document, same information**: Remove duplicate, keep one version
2. **Same document, complementary information**: Merge into single fact entry or keep as separate atomic facts
3. **Different documents, same event**: Keep both with their respective sources (don't merge across documents)
4. **Conflicting information**: Keep both facts and note the discrepancy in your report to the user
5. **Uncertain cases**: Ask the user for guidance using AskUserQuestion tool
