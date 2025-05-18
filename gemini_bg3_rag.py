# gemini_assisted_search.py
import google.generativeai as genai
import os
import re  # For parsing Gemini's re-ranked output
from dotenv import load_dotenv
# Ensure this import matches your filename (e.g., search_data.py)
from find_matching_wiki_pages import search_documents

# Max number of keywords to display per page in the prompt to Gemini for re-ranking
MAX_KEYWORDS_PER_PAGE_IN_PROMPT = 7
# Max number of top re-ranked pages to use for generating the final answer
MAX_PAGES_FOR_ANSWERING = 1  # Start with 1, can be increased


def format_local_results_for_rerank_prompt(pages: list[dict]) -> str:
    """
    Formats the list of pages (full documents) into a string
    suitable for inclusion in the re-ranking prompt for Gemini.
    Includes title, URL, and associated keywords with weights.
    """
    if not pages:
        return "No specific pages found in the local knowledge base."

    formatted_string = "Locally found pages from my knowledge base:\n\n"
    for i, page in enumerate(pages, 1):  # page is a full document dictionary
        formatted_string += f"{i}. Title: {page.get('title', 'N/A')}\n"
        formatted_string += f"   URL: {page.get('url', 'N/A')}\n"

        doc_keywords_with_weights = page.get('keywords', [])
        if doc_keywords_with_weights:
            keywords_to_display = []
            for kw_entry in doc_keywords_with_weights[:MAX_KEYWORDS_PER_PAGE_IN_PROMPT]:
                if isinstance(kw_entry, (list, tuple)) and len(kw_entry) == 2:
                    kw_str = str(kw_entry[0])
                    try:
                        kw_weight = float(kw_entry[1])
                        keywords_to_display.append(f"{kw_str} (weight: {kw_weight:.2f})")
                    except (ValueError, TypeError):
                        keywords_to_display.append(f"{kw_str} (weight: N/A)")
                elif isinstance(kw_entry, str):
                    keywords_to_display.append(kw_entry)
            if keywords_to_display:
                formatted_string += f"   Associated Keywords: {', '.join(keywords_to_display)}\n"
        formatted_string += "\n"
    return formatted_string


def construct_rerank_prompt(original_user_query: str, local_search_results_str: str) -> str:
    """
    Constructs the prompt for Gemini to re-rank local search results.
    """
    # This prompt is the same as your previous version
    prompt = f"""
Original User Query: "{original_user_query}"

Based on this query, my local system performed an initial search and retrieved the following potentially relevant web pages from my knowledge base. Each page is listed with its title, URL, and a selection of its most relevant keywords along with their importance weights (as determined by my local system):

{local_search_results_str}

Your Task:
Please carefully analyze the "Original User Query" and the provided list of "Locally found pages."
For each page, consider its title, URL, and especially its "Associated Keywords" and their "weights" to determine its relevance to the original query.
Your goal is to re-rank these provided pages and select up to the top 10 most relevant pages that directly address the user's query.

Output Format:
- If relevant pages are found, return them as a numbered list. For each item, include ONLY the original "Title" and "URL".
- The URL should be on a new line, prefixed with "   URL: ".
- If you determine that NONE of the provided pages are sufficiently relevant, please state that clearly.

Example of desired output format (if relevant pages are found):
1. Title: Example Page Title 1
   URL: http://example.com/page1
2. Title: Example Page Title 2
   URL: http://example.com/page2
"""
    return prompt


def parse_reranked_results(gemini_response_text: str) -> list[str]:
    """
    Parses Gemini's re-ranked output to extract URLs.
    Expects format like:
    1. Title: Some Title
       URL: http://some.url/
    """
    urls = []
    # Regex to find "URL: http..." or "URL: https..."
    # It captures the URL part.
    url_pattern = re.compile(r"^\s*URL:\s*(https?://[^\s]+)", re.MULTILINE | re.IGNORECASE)
    matches = url_pattern.findall(gemini_response_text)
    for url in matches:
        urls.append(url.strip())
    return urls


def get_content_for_answering(reranked_urls: list[str], all_local_pages: list[dict]) -> str:
    """
    Retrieves the 'text' content for the top N re-ranked URLs from the
    list of all_local_pages (which are full document objects).
    """
    content_to_provide = ""
    pages_found = 0
    for target_url in reranked_urls[:MAX_PAGES_FOR_ANSWERING]:
        found_doc = None
        for doc in all_local_pages:
            if doc.get('url') == target_url:
                found_doc = doc
                break

        if found_doc:
            pages_found += 1
            page_text = found_doc.get('text', '')
            if page_text:
                content_to_provide += f"\n\n--- Content from {found_doc.get('title', 'Unknown Title')} ({target_url}) ---\n"
                content_to_provide += page_text
            else:
                content_to_provide += f"\n\n--- No text content found for {found_doc.get('title', 'Unknown Title')} ({target_url}) ---\n"
        else:
            print(f"Warning: Could not find local document for re-ranked URL: {target_url}")

    if not pages_found:
        return "No content could be retrieved for the top re-ranked pages."
    return content_to_provide


def construct_answer_prompt(original_user_query: str, context_text: str) -> str:
    """
    Constructs the prompt for Gemini to answer the user's query based on provided context.
    """
    prompt = f"""
User Query: "{original_user_query}"

Provided Context from relevant document(s):
--- START OF CONTEXT ---
{context_text}
--- END OF CONTEXT ---

Your Task:
Based *only* on the "Provided Context" above, please answer the "User Query".
If the context does not contain enough information to answer the query, please state that you cannot answer based on the provided information.
Do not use any external knowledge.
Be comprehensive if the context allows.
"""
    return prompt


def main():
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:  # ... (API key check)
        print("Error: GEMINI_API_KEY not found...")
        exit(1)

    try:  # ... (genai.configure)
        genai.configure(api_key=api_key)
    except Exception as e:
        print(f"Error configuring SDK: {e}")
        exit(1)

    model_name = os.environ.get("DEFAULT_MODEL_NAME", "gemini-1.5-flash-latest")  # Use a capable model

    try:  # ... (model initialization)
        model = genai.GenerativeModel(model_name)
        print(f"Successfully initialized model: {model_name}")
    except Exception as e:
        print(f"Error initializing model '{model_name}': {e}")
        # ... (your detailed error handling for model init)
        exit(1)

    print(f"\nGemini Assisted Search & Answer. Model: {model_name}. Type 'quit' or 'exit' to stop.")

    while True:
        try:
            user_query = input("\nYour search query: ")
        except EOFError:
            print("\nExiting (EOF)."); break
        except KeyboardInterrupt:
            print("\nExiting (Interrupt)."); break

        if user_query.lower() in ['quit', 'exit']: break
        if not user_query.strip(): print("Query cannot be empty."); continue

        # --- Stage 1: Local Search ---
        print("\nStep 1: Performing local search...")
        # local_pages now contains FULL document objects, including 'text'
        local_pages = search_documents(user_query)

        if not local_pages:
            print("No pages found by local search. Cannot proceed to re-ranking or answering.")
            # Optionally, you could still send user_query directly to Gemini for a general answer here
            # For now, we'll stop if local search yields nothing.
            continue

        print(f"Found {len(local_pages)} potential matches locally.")

        # --- Stage 2: Gemini Re-ranking ---
        print("\nStep 2: Preparing for Gemini re-ranking...")
        rerank_context_str = format_local_results_for_rerank_prompt(local_pages)
        rerank_prompt = construct_rerank_prompt(user_query, rerank_context_str)

        # print("\n--- Re-rank Prompt for Gemini ---") # Debug
        # print(rerank_prompt)
        # print("--- End of Re-rank Prompt ---")

        print("Asking Gemini to re-rank the local results...")
        try:
            rerank_response = model.generate_content(rerank_prompt)

            reranked_urls = []
            if rerank_response.prompt_feedback and rerank_response.prompt_feedback.block_reason:
                reason = rerank_response.prompt_feedback.block_reason_message or rerank_response.prompt_feedback.block_reason
                print(f"Re-ranking blocked. Reason: {reason}")
            elif rerank_response.parts:
                print("\nGemini's Re-ranked Pages (Title/URL):")
                print("-" * 20)
                print(rerank_response.text)  # Show what Gemini returned
                print("-" * 20)
                reranked_urls = parse_reranked_results(rerank_response.text)
                if not reranked_urls:
                    print("Could not parse any URLs from Gemini's re-ranking response.")
            else:
                print("No text in re-ranking response and not explicitly blocked.")

            if not reranked_urls:
                print("No pages were successfully re-ranked by Gemini or parsing failed. Cannot proceed to answering.")
                continue

            print(f"Successfully extracted {len(reranked_urls)} re-ranked URLs.")

        except Exception as e:
            print(f"An error occurred during Gemini re-ranking: {e}")
            continue

        # --- Stage 3: Content Retrieval & Gemini Answering ---
        print(f"\nStep 3: Retrieving content for top {MAX_PAGES_FOR_ANSWERING} re-ranked page(s)...")
        # Pass ALL local_pages so get_content_for_answering can find the full doc by URL
        context_for_answering = get_content_for_answering(reranked_urls, local_pages)

        if "No content could be retrieved" in context_for_answering or not context_for_answering.strip():
            print("Could not retrieve sufficient content for the top re-ranked pages. Cannot ask Gemini to answer.")
            continue

        # print("\n--- Context for Answering ---") # Debug
        # print(context_for_answering)
        # print("--- End of Context ---")

        print("Asking Gemini to answer the query based on retrieved content...")
        answer_prompt_str = construct_answer_prompt(user_query, context_for_answering)

        # print("\n--- Answer Prompt for Gemini ---") # Debug
        # print(answer_prompt_str)
        # print("--- End of Answer Prompt ---")

        try:
            final_answer_response = model.generate_content(answer_prompt_str)
            print("\nGemini's Answer based on Context:")
            print("=" * 30)
            if final_answer_response.prompt_feedback and final_answer_response.prompt_feedback.block_reason:
                reason = final_answer_response.prompt_feedback.block_reason_message or final_answer_response.prompt_feedback.block_reason
                print(f"Answering blocked. Reason: {reason}")
            elif final_answer_response.parts:
                print(final_answer_response.text)
            else:
                print("No text in final answer response and not explicitly blocked.")
            print("=" * 30)
        except Exception as e:
            print(f"An error occurred during Gemini answering: {e}")

    print("\nExiting Gemini Assisted Search & Answer script.")


if __name__ == "__main__":
    main()