# Process Next Letter

Run the automated letter processing workflow to extract genealogical facts.

## Workflow Steps

Execute the workflow script to get the next letter:

```bash
./scripts/process_next_letter.sh
```

Then follow these steps:

1. **Read the script output** to extract:
   - Letter path
   - Letter filename
   - Date code
   - Source citation

2. **Launch fact-extractor agent** with the Task tool:
   - subagent_type: "fact-extractor"
   - prompt: "Extract genealogical facts from the letter at [PATH]. Create a temporary JSON file with the extracted facts."
   - The agent will create `/tmp/facts_extract_[FILENAME].json` and report the path

3. **Launch data verification agents** (IMPORTANT: specify the temp file path):
   - fact-source-verifier:
     - prompt: "Verify the facts in /tmp/facts_extract_[FILENAME].json against their source document"
   - fact-irrelevant-verifier:
     - prompt: "Clean /tmp/facts_extract_[FILENAME].json by removing facts irrelevant to the Rosenberg lineage"
   - These agents will read and update the temp file before merging

4. **Merge temporary facts into facts.json**:
   ```bash
   python3 scripts/merge_facts.py /tmp/facts_extract_[FILENAME].json
   ```
   - Replace [FILENAME] with the base name from step 1 (e.g., "1327 may 4")
   - This merges the temp file, sorts chronologically, and validates structure

5. **Launch fact-syntax-verifier agent** with the Task tool:
    - subagent_type: "fact-syntax-verifier"
    - prompt: "Verify the JSON structure, chronological sorting, and quality of data/facts.json after the recent update."

6. **After agents complete successfully**, remove the letter from report:
   ```bash
   ./scripts/remove_letter_from_report.sh "[FILENAME]"
   ```

7. **Report results** to user:
   - Number of facts extracted
   - Validation status
   - Remaining letters count
   - Next letter to process (if any)

## Important Notes

- Always wait for agents to complete before removing letter from report
- If agents fail, do NOT remove the letter - report the error to user
- Process letters sequentially (one at a time)
- Commit changes after processing batches of letters
