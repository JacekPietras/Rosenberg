#!/bin/bash

# Convert letter date format to ISO format (YYYY-MM-DD)
# Input: date string like "1300 mai 17" or "1327 may 4" or "1330"
# Output: ISO format like "1300-05-17" or "1327-05-04" or "1330"

# Function to convert month name to number
month_to_number() {
    local month="$1"
    case "$month" in
        jan|januar|january|januari) echo "01" ;;
        feb|febr|februar|february|febuary) echo "02" ;;
        mrz|marz|march|mart) echo "03" ;;
        apr|april) echo "04" ;;
        mai|may) echo "05" ;;
        juni|june) echo "06" ;;
        juli|july) echo "07" ;;
        aug|august|auy) echo "08" ;;
        sep|sept|september) echo "09" ;;
        okt|oktober|october) echo "10" ;;
        nov|november) echo "11" ;;
        dez|dec|dezember|december) echo "12" ;;
        *) echo "" ;;
    esac
}

# Convert date string to ISO format
convert_to_iso() {
    local filename="$1"
    
    # Extract year (first 4 digits)
    local year=$(echo "$filename" | grep -o '^[0-9]\{4\}')
    
    if [ -z "$year" ]; then
        echo ""
        return
    fi
    
    # Remove location suffix (e.g., " heidelberg", " ehrenfels") and duplicate suffix (e.g., "_2", "_3")
    local rest=$(echo "$filename" | sed "s/^$year *//" | sed 's/_[0-9]*$//' | sed 's/ [a-z]*$//')

    if [ -z "$rest" ]; then
        # Year only
        echo "$year"
    else
        # Extract month and day
        local month_name=$(echo "$rest" | awk '{print $1}')
        # For date ranges, take the first day number (start of range)
        local day=$(echo "$rest" | awk '{for(i=2;i<=NF;i++) if($i ~ /^[0-9]+$/) {print $i; exit}}')
        
        if [ -n "$month_name" ] && [ -n "$day" ]; then
            local month_num=$(month_to_number "$month_name")
            if [ -n "$month_num" ]; then
                # Pad day with zero if needed
                local day_padded=$(printf "%02d" "$day" 2>/dev/null || echo "$day")
                echo "$year-$month_num-$day_padded"
            else
                echo ""
            fi
        elif [ -n "$month_name" ]; then
            local month_num=$(month_to_number "$month_name")
            if [ -n "$month_num" ]; then
                echo "$year-$month_num"
            else
                echo ""
            fi
        else
            echo "$year"
        fi
    fi
}

# Main: read from stdin or arguments
if [ $# -eq 0 ]; then
    # Read from stdin
    while IFS= read -r line; do
        result=$(convert_to_iso "$line")
        if [ -n "$result" ]; then
            echo "$result"
        fi
    done
else
    # Process arguments
    for arg in "$@"; do
        result=$(convert_to_iso "$arg")
        if [ -n "$result" ]; then
            echo "$result"
        fi
    done
fi

