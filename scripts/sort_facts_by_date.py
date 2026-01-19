#!/usr/bin/env python3
"""
Sort facts.json entries by date to prevent hallucinations.
Reads JSON, sorts by date field, writes back to file.
"""

import json
from datetime import datetime
import sys
import os

def parse_date(date_str):
    """Parse date string into datetime object for sorting."""
    try:
        # Handle YYYY-MM-DD format
        if len(date_str) == 10 and date_str.count('-') == 2:
            return datetime.strptime(date_str, '%Y-%m-%d')
        # Handle YYYY-MM format (treat as first day of month)
        elif len(date_str) == 7 and date_str.count('-') == 1:
            return datetime.strptime(date_str + '-01', '%Y-%m-%d')
        # Handle YYYY format
        elif len(date_str) == 4 and date_str.isdigit():
            return datetime.strptime(date_str, '%Y')
        else:
            print(f"Warning: Unexpected date format: {date_str}")
            return datetime.strptime(date_str[:4], '%Y')  # Fallback to year only
    except ValueError as e:
        print(f"Error parsing date '{date_str}': {e}")
        return datetime.min  # Put unparseable dates at the beginning

def main():
    facts_file = 'data/facts.json'
    
    # Check if file exists
    if not os.path.exists(facts_file):
        print(f"Error: {facts_file} not found")
        sys.exit(1)
    
    # Read the JSON file
    try:
        with open(facts_file, 'r', encoding='utf-8') as f:
            facts = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {facts_file}: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading {facts_file}: {e}")
        sys.exit(1)
    
    # Validate that facts is a list
    if not isinstance(facts, list):
        print(f"Error: Expected a list in {facts_file}, got {type(facts)}")
        sys.exit(1)
    
    print(f"Read {len(facts)} entries from {facts_file}")
    
    # Sort by date
    try:
        facts_sorted = sorted(facts, key=lambda x: parse_date(x.get('date', '')))
        print(f"Sorted {len(facts_sorted)} entries by date")
    except Exception as e:
        print(f"Error sorting facts: {e}")
        sys.exit(1)
    
    # Write back to file
    try:
        with open(facts_file, 'w', encoding='utf-8') as f:
            json.dump(facts_sorted, f, indent=2, ensure_ascii=False)
        print(f"Successfully wrote sorted facts to {facts_file}")
    except Exception as e:
        print(f"Error writing to {facts_file}: {e}")
        sys.exit(1)
    
    # Print first few dates to verify sorting
    print("\nFirst 10 dates after sorting:")
    for i, fact in enumerate(facts_sorted[:10]):
        print(f"  {i+1}. {fact.get('date', 'NO_DATE')} - {fact.get('source', 'NO_SOURCE')[:50]}...")

if __name__ == '__main__':
    main()
