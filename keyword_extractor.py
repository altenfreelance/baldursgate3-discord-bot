import json
import random
from keybert import KeyBERT

def extract_keyword_from_user_input():
    """
    Prompts the user for a string and extracts keywords from it.
    """
    user_prompt = input("Please enter a string: ")

    kw_model = KeyBERT()
    keywords = kw_model.extract_keywords(user_prompt)
    print("--- Keywords from your input ---")
    print(keywords)

def extract_keywords_from_file_samples(filepath="data/raw/bg3_wiki_data.jsonl", num_samples=3):
    """
    Reads a JSONL file, extracts text from random samples,
    prints the text, and then extracts and prints keywords from that text.
    """
    all_entries = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    all_entries.append(json.loads(line))
                except json.JSONDecodeError:
                    print(f"Warning: Could not decode JSON from line: {line.strip()}")
    except FileNotFoundError:
        print(f"Error: File not found at {filepath}")
        return
    except Exception as e:
        print(f"An error occurred while reading the file: {e}")
        return

    if not all_entries:
        print(f"No data found or loaded from {filepath}")
        return

    # Ensure we don't try to sample more items than available
    actual_samples_to_take = min(num_samples, len(all_entries))
    if actual_samples_to_take < num_samples:
        print(f"Warning: Requested {num_samples} samples, but only {len(all_entries)} entries are available. Using {actual_samples_to_take}.")

    if actual_samples_to_take == 0:
        print("No entries to sample from.")
        return

    selected_entries = random.sample(all_entries, actual_samples_to_take)

    kw_model = KeyBERT() # Initialize model once

    print(f"\n--- Extracting keywords from {actual_samples_to_take} random samples from {filepath} ---")
    for i, entry in enumerate(selected_entries):
        print(f"\n--- Sample {i+1}/{actual_samples_to_take} ---")
        text_content = entry.get("text") # Safely get the 'text' field

        if text_content:
            print("Original Text:")
            print(text_content)
            print("-" * 20)

            keywords = kw_model.extract_keywords(text_content)
            print("Extracted Keywords:")
            print(keywords)
        else:
            print(f"Warning: Entry did not contain a 'text' field or text was empty. Entry: {entry}")
        print("=" * 30)


if __name__ == "__main__":
    # Example 1: Extract keywords from user input
    # print("--- Running keyword extraction from user input ---")
    # extract_keyword_from_user_input()
    # print("\n" + "="*50 + "\n")

    # Example 2: Extract keywords from random file samples
    print("--- Running keyword extraction from file samples ---")
    extract_keywords_from_file_samples(filepath="data/raw/bg3_wiki_data.jsonl", num_samples=3)