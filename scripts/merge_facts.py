#!/usr/bin/env python3
"""
Merges temporary facts JSON file into data/facts.json
Then sorts the facts chronologically

Usage: python3 scripts/merge_facts.py <temp_facts_file>
"""

import json
import sys
import os
from pathlib import Path

def merge_facts(temp_file_path, facts_file_path="data/facts.json"):
    """Merge temporary facts into main facts.json file"""

    # Validate temp file exists
    if not os.path.exists(temp_file_path):
        print(f"ERROR: Temporary facts file not found: {temp_file_path}", file=sys.stderr)
        sys.exit(1)

    # Read temporary facts
    try:
        with open(temp_file_path, 'r', encoding='utf-8') as f:
            temp_facts = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in temporary facts file: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to read temporary facts file: {e}", file=sys.stderr)
        sys.exit(1)

    # Validate temp_facts is a list
    if not isinstance(temp_facts, list):
        print("ERROR: Temporary facts file must contain a JSON array", file=sys.stderr)
        sys.exit(1)

    # Read existing facts.json (or create empty array if it doesn't exist)
    existing_facts = []
    if os.path.exists(facts_file_path):
        try:
            with open(facts_file_path, 'r', encoding='utf-8') as f:
                existing_facts = json.load(f)
        except json.JSONDecodeError as e:
            print(f"ERROR: Invalid JSON in {facts_file_path}: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"ERROR: Failed to read {facts_file_path}: {e}", file=sys.stderr)
            sys.exit(1)

    # Validate existing_facts is a list
    if not isinstance(existing_facts, list):
        print(f"ERROR: {facts_file_path} must contain a JSON array", file=sys.stderr)
        sys.exit(1)

    # Count new facts
    new_count = len(temp_facts)
    if new_count == 0:
        print("WARNING: No facts to merge from temporary file", file=sys.stderr)
        return

    # Merge: prepend new facts to existing facts
    merged_facts = temp_facts + existing_facts

    # Write merged facts back to facts.json
    try:
        with open(facts_file_path, 'w', encoding='utf-8') as f:
            json.dump(merged_facts, f, indent=2, ensure_ascii=False)
            f.write('\n')  # Add trailing newline
    except Exception as e:
        print(f"ERROR: Failed to write to {facts_file_path}: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"✓ Merged {new_count} new fact entries into {facts_file_path}")
    print(f"  Total entries: {len(merged_facts)}")

    # Now sort the facts chronologically
    print("✓ Sorting facts chronologically...")

    # Import and run the sort function from sort_facts_by_date.py
    script_dir = Path(__file__).parent
    sort_script = script_dir / "sort_facts_by_date.py"

    if sort_script.exists():
        # Run the sort script
        os.system(f'python3 "{sort_script}"')
    else:
        print(f"WARNING: Sort script not found at {sort_script}", file=sys.stderr)
        print("Facts have been merged but NOT sorted.", file=sys.stderr)

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/merge_facts.py <temp_facts_file>", file=sys.stderr)
        sys.exit(1)

    temp_file = sys.argv[1]
    merge_facts(temp_file)

if __name__ == "__main__":
    main()
