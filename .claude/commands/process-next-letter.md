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
   - prompt: "Extract genealogical facts from the letter at [PATH] following the guidelines in prompts/prompt.txt. Append results to data/facts.json."

3. **Launch fact-syntax-verifier agent** with the Task tool:
   - subagent_type: "fact-syntax-verifier"
   - prompt: "Verify the JSON structure, chronological sorting, and quality of data/facts.json after the recent update."

4. **Optional agents** (launch if needed):
   - fact-source-verifier: Verify facts against source document
   - fact-irrelevant-verifier: Filter non-genealogical content

5. **After agents complete successfully**, remove the letter from report:
   ```bash
   ./scripts/remove_letter_from_report.sh "[FILENAME]"
   ```

6. **Report results** to user:
   - Number of facts extracted
   - Validation status
   - Remaining letters count
   - Next letter to process (if any)

## Important Notes

- Always wait for agents to complete before removing letter from report
- If agents fail, do NOT remove the letter - report the error to user
- Process letters sequentially (one at a time)
- Commit changes after processing batches of letters
