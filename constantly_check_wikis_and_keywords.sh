#!/bin/bash

# Define the files to monitor
keywords_file="data/generated/bg3_wiki_data_keywords.jsonl"
wikis_file="data/raw/bg3_wiki_data.jsonl"

# Function to get the number of lines in a file
get_file_line_count() {
  if [ ! -f "$1" ]; then
    echo "Error: File not found: $1"
    return 0
  fi
  if ! command -v wc >/dev/null 2>&1; then
    echo "Error: wc command not found. Please install coreutils."
    return 0
  fi
  line_count=$(wc -l < "$1" 2>/dev/null) # Redirect stderr to /dev/null
  if [[ $? -ne 0 ]]; then
    echo "Error running wc -l on $1.  wc exited with code $?"
    return 0
  fi

  # Extract the number
  line_count=$(echo "$line_count" | awk '{print $1}')
  if [[ -z "$line_count" || ! "$line_count" =~ ^[0-9]+$ ]]; then
    echo "Error: Could not parse line count from wc output for $1: $line_count"
    return 0
  fi
  echo "$line_count"
}

# Function to get human-readable file size
get_human_readable_size() {
  if [ ! -f "$1" ]; then
    echo "N/A"
    return
  fi
  if ! command -v du >/dev/null 2>&1; then
    echo "Error: du command not found. Please install coreutils."
    echo "N/A"
    return
  fi
  file_size=$(du -h "$1" 2>/dev/null | awk '{print $1}')
  if [[ $? -ne 0 ]]; then
    echo "Error running du -h on $1. du exited with code $?"
    echo "N/A"
    return
  fi
  echo "$file_size"
}

# Main loop
while true; do
  keywords_count=$(get_file_line_count "$keywords_file")
  wikis_count=$(get_file_line_count "$wikis_file")
  keywords_size=$(get_human_readable_size "$keywords_file")
  wikis_size=$(get_human_readable_size "$wikis_file")

  echo "1) Keywords generated for $keywords_count pages ($keywords_size)"
  echo "2) Wikis scraped: $wikis_count ($wikis_size)"
  echo "------------------------------"
  sleep 25
done