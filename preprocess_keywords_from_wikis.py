import json
import os

from keyword_extractor import extract_keywords  # Assuming this is in your Python path or same directory

# Define file paths
RAW_DATA_FILE = 'data/raw/bg3_wiki_data.jsonl'
GENERATED_DATA_FILE = 'data/generated/bg3_wiki_data_keywords.jsonl'

def load_existing_urls(filepath):
    """
    Loads all URLs from an existing generated JSONL file.
    Returns a set of URLs.
    """
    existing_urls = set()
    if not os.path.exists(filepath):
        return existing_urls

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if 'url' in entry:
                        existing_urls.add(entry['url'])
                except json.JSONDecodeError:
                    print(f"Warning: Could not parse line in existing generated file {filepath}. Skipping line.")
    except Exception as e:
        print(f"Error reading existing generated file {filepath}: {e}")
    return existing_urls

def preprocess_jsonl():
    """
    Reads the raw JSONL file, extracts keywords from the 'text' field
    if the URL is not already processed, and writes a new JSONL file
    with 'url', 'title', 'keywords', 'text'.
    Appends to the generated file if it already exists.
    """
    os.makedirs(os.path.dirname(GENERATED_DATA_FILE), exist_ok=True)

    print("Loading existing URLs from generated file (if any)...")
    # Load URLs that have already been processed and are in the generated file
    # We will append to the generated file, so we need to know what's already there.
    existing_urls = load_existing_urls(GENERATED_DATA_FILE)
    print(f"Found {len(existing_urls)} existing URLs in {GENERATED_DATA_FILE}.")

    print(f"Starting preprocessing of {RAW_DATA_FILE}...")
    processed_count = 0
    skipped_count = 0

    try:
        # Open raw file for reading, and generated file for appending ('a')
        # If GENERATED_DATA_FILE doesn't exist, 'a' will create it.
        with open(RAW_DATA_FILE, 'r', encoding='utf-8') as infile, \
                open(GENERATED_DATA_FILE, 'a', encoding='utf-8') as outfile:

            for line_number, line in enumerate(infile, 1):
                try:
                    entry = json.loads(line.strip())

                    url = entry.get('url', '')
                    title = entry.get('title', '')
                    text_content = entry.get('text', '')

                    if not url:
                        print(f"Warning: Line {line_number} has no URL. Skipping.")
                        continue

                    # Check if this URL has already been processed
                    if url in existing_urls:
                        # print(f"Skipping already processed URL: {url}") # Optional: for verbose logging
                        skipped_count += 1
                        continue

                    # Extract keywords from the text content with backoff
                    # We use the same function as for user input for consistency here
                    # but you could have a different, more aggressive one for documents
                    print(f"Processing URL: {url} (Line {line_number})")
                    keywords = extract_keywords(text_content)

                    # Create the new entry with the specified order
                    processed_entry = {
                        'url': url,
                        'title': title,
                        'keywords': keywords,
                        'text': text_content  # Keeping original text as requested
                    }

                    outfile.write(json.dumps(processed_entry) + '\n')
                    existing_urls.add(url)  # Add to our set of processed URLs for this run
                    processed_count += 1

                except json.JSONDecodeError:
                    print(f"Warning: Could not parse line {line_number} in {RAW_DATA_FILE}. Skipping.")
                except Exception as e:
                    print(
                        f"Error processing line {line_number} for URL '{entry.get('url', 'N/A')}': {e}. Entry: {line.strip()}")

    except FileNotFoundError:
        print(f"Error: Raw data file {RAW_DATA_FILE} not found.")
        print("Please make sure the file exists or run with a command to create dummy data.")
        return
    except Exception as e:
        print(f"An unexpected error occurred during preprocessing: {e}")
        return

    print("\nPreprocessing complete.")
    print(f"Newly processed and added entries: {processed_count}")
    print(f"Entries skipped (already existed): {skipped_count}")
    print(f"Generated/updated keyword data saved to {GENERATED_DATA_FILE}")


if __name__ == "__main__":
    preprocess_jsonl()