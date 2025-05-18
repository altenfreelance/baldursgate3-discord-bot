# search_data.py
import json
import os
import re

from keyword_extractor import extract_keywords

GENERATED_DATA_FILE = 'data/generated/bg3_wiki_data_keywords.jsonl'
SEARCH_QUERY_BLACKLIST = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "should",
    "can", "could", "may", "might", "must", "am",
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves",
    "you", "your", "yours", "yourself", "yourselves",
    "he", "him", "his", "himself", "she", "her", "hers", "herself",
    "it", "its", "itself", "they", "them", "their", "theirs", "themselves",
    "what", "which", "who", "whom", "this", "that", "these", "those",
    "to", "of", "at", "by", "for", "with", "about", "against", "between",
    "into", "through", "during", "before", "after", "above", "below",
    "from", "up", "down", "in", "out", "on", "off", "over", "under",
    "again", "further", "then", "once", "here", "there", "when", "where",
    "why", "how", "all", "any", "both", "each", "few", "more", "most",
    "other", "some", "such", "no", "nor", "not", "only", "own", "same",
    "so", "than", "too", "very", "s", "t", "just", "don", "now",
    "get", "make", "go", "see", "know", "take", "find", "tell",
    "ask", "work", "seem", "feel", "try", "leave", "call", "give",
    "let", "put", "say", "set", "look", "want", "need",
    "use"  # Added 'use' as per your example
    # Add other words like 'page', 'article', 'information', 'about', 'help'
    # if they are too generic for your search context.
}
MIN_USER_KEYWORD_LENGTH = 2


def search_documents(user_query: str) -> list[dict]:
    # ... (this function's content remains exactly the same as your last version)
    # It already returns a list of full document dictionaries: [item[2] for item in sorted_matches]
    # where item[2] is the 'doc' object.
    if not os.path.exists(GENERATED_DATA_FILE):
        print(f"Error: Preprocessed data file {GENERATED_DATA_FILE} not found.")
        print("Please run the preprocess_data.py script first.")
        return []

    user_query_keywords_with_weights = extract_keywords(user_query)

    print(f"Keywords initially extracted from user query (by extract_keywords): {user_query_keywords_with_weights}")

    if not user_query_keywords_with_weights:
        print(
            "Since no keywords were effectively extracted (or extract_keywords returned an empty list), cannot proceed with search.")
        return []

    processed_user_keyword_strings = []
    for item in user_query_keywords_with_weights:
        if isinstance(item, (list, tuple)) and len(item) > 0 and isinstance(item[0], str):
            keyword_str_lower = item[0].lower()
            if keyword_str_lower not in SEARCH_QUERY_BLACKLIST and len(keyword_str_lower) >= MIN_USER_KEYWORD_LENGTH:
                processed_user_keyword_strings.append(keyword_str_lower)

    user_keywords_set_lower = set(processed_user_keyword_strings)

    if not user_keywords_set_lower:
        print("No valid (non-blacklisted, sufficient length) keywords remain after filtering user query.")
        return []

    print(f"Searching for user keyword strings (filtered, lowercase): {user_keywords_set_lower}")

    potential_matches = []

    try:
        with open(GENERATED_DATA_FILE, 'r', encoding='utf-8') as infile:
            for line_number, line in enumerate(infile, 1):
                try:
                    doc = json.loads(line.strip())
                    title_lower = doc.get('title', '').lower()
                    doc_keywords_with_weights = doc.get('keywords', [])

                    is_title_match = False
                    for user_kw_lower_str in user_keywords_set_lower:
                        pattern = r'\b' + re.escape(user_kw_lower_str) + r'\b'
                        if re.search(pattern, title_lower):
                            is_title_match = True
                            break

                    max_matching_keyword_weight = 0.0
                    found_keyword_in_list = False

                    if isinstance(doc_keywords_with_weights, list):
                        for kw_entry in doc_keywords_with_weights:
                            if isinstance(kw_entry, list) and len(kw_entry) == 2 and isinstance(kw_entry[0], str):
                                doc_kw_str_lower = kw_entry[0].lower()
                                try:
                                    doc_kw_weight = float(kw_entry[1])
                                except (ValueError, TypeError):
                                    doc_kw_weight = 0.0
                                if doc_kw_str_lower in user_keywords_set_lower:
                                    found_keyword_in_list = True
                                    max_matching_keyword_weight = max(max_matching_keyword_weight, doc_kw_weight)

                    if is_title_match or found_keyword_in_list:
                        title_match_priority_score = 1 if is_title_match else 0
                        effective_weight = max_matching_keyword_weight if found_keyword_in_list else 0.0
                        potential_matches.append((title_match_priority_score, effective_weight, doc)) # doc is the full document
                except json.JSONDecodeError:
                    print(f"Warning: Could not parse line {line_number} in {GENERATED_DATA_FILE}. Skipping.")
                except (TypeError, ValueError) as e:
                    print(
                        f"Warning: Data format error in line {line_number} for keywords: {e}. Entry: {line.strip()[:100]}...")
                except Exception as e:
                    print(f"Error processing line {line_number} for search: {e}. Entry: {line.strip()[:100]}...")
    except FileNotFoundError:
        print(f"Error: Preprocessed data file {GENERATED_DATA_FILE} not found during search.")
        return []

    sorted_matches = sorted(potential_matches, key=lambda x: (-x[0], -x[1]))
    return [item[2] for item in sorted_matches] # Returns a list of full document dicts


if __name__ == "__main__":
    if not os.path.exists(GENERATED_DATA_FILE):
        print(f"Preprocessed data file {GENERATED_DATA_FILE} not found.")
        print("Please run `python preprocess_data.py` first.")
    else:
        while True:
            query = input("\nEnter your search query (or 'quit' to exit): ")
            if query.lower() == 'quit':
                break
            if not query.strip():
                print("Please enter a search term.")
                continue
            results = search_documents(query)
            if results:
                print(f"\nFound {len(results)} matching document(s) (sorted by relevance):")
                for i, doc in enumerate(results, 1):
                    print(f"\n--- Result {i} ---")
                    print(f"Title: {doc.get('title', 'N/A')}")
                    print(f"URL: {doc.get('url', 'N/A')}")
            else:
                print("No matching documents found.")
            print("-" * 30)