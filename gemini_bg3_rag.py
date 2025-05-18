# gemini_assisted_search.py
import google.generativeai as genai
import os
import re
import argparse
from dotenv import load_dotenv
from find_matching_wiki_pages import search_documents

# Max number of keywords to display per page in the prompt to Gemini for re-ranking
MAX_KEYWORDS_PER_PAGE_IN_PROMPT = 7
# Max number of top re-ranked pages to use for generating the final answer
MAX_PAGES_FOR_ANSWERING = 3
# Number of recent chat history turns to provide to the LLM for search guidance
NUM_HISTORY_TURNS_FOR_GUIDANCE = 4  # e.g., last 2 user messages and 2 model responses
# Topic hint for the LLM when asking for search guidance
KNOWLEDGE_BASE_TOPIC = "Baldur's Gate 3 game information"


# --- Helper function to format chat history ---
def format_chat_history_snippet(history: list, num_turns: int) -> str:
    """Formats the last N turns of chat history into a readable string.
    Expects history to be a list of google.generativeai.types.Content objects.
    """
    if not history:
        return "No prior conversation history."

    snippet = "Recent Conversation Snippet:\n"
    # Take the last `num_turns` messages. Each 'turn' in history is one Content object.
    relevant_history = history[-num_turns:]
    for message_content in relevant_history:  # Renamed to avoid confusion with 'message' dict
        # Access attributes directly
        role = getattr(message_content, 'role', 'unknown').capitalize()

        text_parts_collected = []
        # message_content.parts is a list of Part objects
        if hasattr(message_content, 'parts') and isinstance(message_content.parts, list):
            for part in message_content.parts:
                # Each part has a 'text' attribute
                if hasattr(part, 'text'):
                    text_parts_collected.append(part.text)

        text = " ".join(text_parts_collected).strip() if text_parts_collected else "[empty message or non-text parts]"
        snippet += f"- {role}: {text}\n"
    return snippet

# --- Functions for RAG pipeline (format_local_results, parse_reranked, get_content, etc.) ---
def format_local_results_for_rerank_prompt(pages: list[dict]) -> str:
    # ... (remains the same)
    if not pages:
        return "No specific pages found in the local knowledge base."
    formatted_string = "Locally found pages from my knowledge base:\n\n"
    for i, page in enumerate(pages, 1):
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
    # ... (remains the same, emphasizes ORIGINAL user query)
    prompt = f"""
Original User Query (for this re-ranking task): "{original_user_query}"

Based on THIS query, my local system performed an initial search and retrieved the following potentially relevant web pages from my knowledge base. Each page is listed with its title, URL, and a selection of its most relevant keywords along with their importance weights (as determined by my local system):

{local_search_results_str}

Your Task:
Please carefully analyze the "Original User Query" (for this re-ranking task) and the provided list of "Locally found pages."
For each page, consider its title, URL, and especially its "Associated Keywords" and their "weights" to determine its relevance to the original query.
Your goal is to re-rank these provided pages and select up to the top 10 most relevant pages that directly address the user's original query.

Output Format:
- If relevant pages are found, return them as a numbered list. For each item, include ONLY the original "Title" and "URL".
- The URL should be on a new line, prefixed with "   URL: ".
- If you determine that NONE of the provided pages are sufficiently relevant, please state that clearly.
"""
    return prompt


def parse_reranked_results(gemini_response_text: str) -> list[str]:
    # ... (remains the same)
    urls = []
    url_pattern = re.compile(r"^\s*URL:\s*(https?://[^\s]+)", re.MULTILINE | re.IGNORECASE)
    matches = url_pattern.findall(gemini_response_text)
    for url in matches:
        urls.append(url.strip())
    return urls


def get_content_for_answering(reranked_urls: list[str], all_local_pages: list[dict], verbose: bool = False) -> str:
    # ... (remains the same)
    content_to_provide = ""
    pages_found = 0
    if not reranked_urls:
        return "No specific documents were identified as relevant by the re-ranking step for the current query."
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
                content_to_provide += f"\n\n--- Context from {found_doc.get('title', 'Unknown Title')} ({target_url}) ---\n"
                content_to_provide += page_text
            else:
                content_to_provide += f"\n\n--- No text content found for {found_doc.get('title', 'Unknown Title')} ({target_url}) ---\n"
        elif verbose:
            print(f"Verbose: Could not find local document for re-ranked URL: {target_url}")
    if not pages_found:
        return "No content could be retrieved for the top re-ranked pages."
    return content_to_provide


def construct_answer_prompt_for_chat_turn(current_user_query: str, context_text: str) -> str:
    # ... (remains the same)
    prompt = f"""
User's current query: "{current_user_query}"

To help answer this current query, I have retrieved the following context from my knowledge base:
--- START OF CONTEXT (for current query) ---
{context_text}
--- END OF CONTEXT (for current query) ---

Your Task:
Considering our ongoing conversation (which you have access to) AND the "CONTEXT (for current query)" provided above, please answer the "User's current query".
- Prioritize the "CONTEXT (for current query)" when it's relevant.
- You may refer to relevant information from our previous exchanges if it helps provide a more complete or nuanced answer to the *current query*.
- If the "CONTEXT (for current query)" and our prior conversation do not contain enough information to answer the current query, please state that.
- Do not use any external knowledge. Be comprehensive if the information allows.
"""
    return prompt


# --- NEW: Function for LLM-Guided Search Query ---
def construct_llm_search_guidance_prompt(user_query: str, history_snippet: str, kb_topic: str) -> str:
    """Constructs a prompt to ask the LLM for a better search query."""
    prompt = f"""The user's current query is: "{user_query}"

My system's initial keyword-based search in a knowledge base about "{kb_topic}" did not find relevant documents for this query.

{history_snippet}

Based on the user's current query AND the recent conversation context (if available), please formulate a single, improved search query string (2-5 words ideally) that is more likely to find relevant documents in the knowledge base.
For example, if the user asked 'which one should I pick?' after a discussion about 'Barbarian subclasses', a good improved query might be 'Barbarian subclass comparison' or 'best Barbarian subclass'.

Output ONLY the improved search query string and nothing else. Do not add any preamble or explanation.
"""
    return prompt


def main():
    parser = argparse.ArgumentParser(description="Gemini Assisted Search & Answer with RAG and Chat.")
    parser.add_argument(
        "-v", "--verbose", action="store_true", default=False,
        help="Enable verbose logging to see intermediate steps and prompts."
    )
    args = parser.parse_args()
    verbose = args.verbose

    if verbose: print("Verbose logging enabled.")

    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found.");
        exit(1)

    try:
        genai.configure(api_key=api_key)
    except Exception as e:
        print(f"Error configuring SDK: {e}"); exit(1)

    model_name = os.environ.get("DEFAULT_MODEL_NAME", "gemini-1.5-flash-latest")
    safety_settings_config = [
        {"category": c, "threshold": "BLOCK_MEDIUM_AND_ABOVE"} for c in [
            "HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH",
            "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"
        ]
    ]

    try:
        model = genai.GenerativeModel(model_name, safety_settings=safety_settings_config)
        print(f"Successfully initialized model: {model_name} with safety settings.")
    except Exception as e:
        print(f"Error initializing model '{model_name}': {e}");
        exit(1)

    print(f"\nGemini Assisted Search & Answer. Model: {model_name}.")
    print(f"Knowledge Base Topic: {KNOWLEDGE_BASE_TOPIC}")
    print("Type '/new' for new chat, 'quit' or 'exit' to stop.")

    chat_session = model.start_chat(history=[])
    print("New chat session started.")

    while True:
        try:
            user_query = input("\nYour query: ")
        except EOFError:
            print("\nExiting (EOF)."); break
        except KeyboardInterrupt:
            print("\nExiting (Interrupt)."); break

        if user_query.lower() in ['quit', 'exit']: break
        if user_query.lower() == '/new':
            chat_session = model.start_chat(history=[])
            print("\n--- New chat session started. ---")
            continue
        if not user_query.strip(): print("Query cannot be empty."); continue

        print("\nStep 1: Performing initial local search...")
        local_pages = search_documents(user_query)  # Expects list of dicts

        # --- NEW: LLM-Guided Search Augmentation ---
        # Trigger if initial search fails (and not first turn, to leverage history for better guidance)
        # Or if initial search fails on first turn, it will use only user_query for guidance.
        if not local_pages:
            if verbose: print("Initial local search failed or yielded no results.")
            print("Attempting LLM-guided search refinement...")

            history_for_guidance = []
            # Ensure chat_session.history is accessed correctly
            # It's a list of Content objects. We need to convert them to dicts for format_chat_history_snippet
            # OR adjust format_chat_history_snippet to handle Content objects directly
            # For now, let's assume format_chat_history_snippet is robust or history is pre-processed
            # The `ChatSession.history` property already returns a list of dict-like structures.
            if chat_session.history:  # Only use history if it exists
                history_for_guidance = chat_session.history

            formatted_hist_snippet = format_chat_history_snippet(history_for_guidance, NUM_HISTORY_TURNS_FOR_GUIDANCE)

            guidance_prompt_str = construct_llm_search_guidance_prompt(user_query, formatted_hist_snippet,
                                                                       KNOWLEDGE_BASE_TOPIC)

            if verbose:
                print("\n--- LLM Search Guidance Prompt ---")
                print(guidance_prompt_str)
                print("--- End of Guidance Prompt ---")

            try:
                guidance_response = model.generate_content(guidance_prompt_str)  # Uses model's default safety

                suggested_query = ""
                if guidance_response.prompt_feedback and guidance_response.prompt_feedback.block_reason:
                    reason = guidance_response.prompt_feedback.block_reason_message or guidance_response.prompt_feedback.block_reason
                    print(f"LLM search guidance was blocked. Reason: {reason}")
                elif guidance_response.parts:
                    suggested_query = guidance_response.text.strip()
                    if verbose: print(f"LLM suggested search query: '{suggested_query}'")
                else:
                    print("LLM search guidance provided no response text and was not blocked.")

                if suggested_query:
                    print(f"Performing local search with LLM-suggested query: '{suggested_query}'...")
                    local_pages = search_documents(suggested_query)  # Use the new query
                    print(f"Found {len(local_pages)} pages after LLM-guided search.")
                else:
                    print("LLM guidance did not result in a usable search query. Proceeding with no local results.")
            except Exception as e:
                print(f"Error during LLM-guided search query generation: {e}")
                print("Proceeding with no local results from initial search.")
        # --- End of LLM-Guided Search Augmentation ---

        context_for_answering = ""
        if not local_pages:
            if verbose: print("No pages found by local search (even after potential augmentation).")
            context_for_answering = "No specific documents were found in the local knowledge base for your current query, even after attempting to refine the search."
        else:
            print(f"Found {len(local_pages)} potential matches locally for '{user_query}' (or augmented query).")
            print("\nStep 2: Preparing for Gemini re-ranking...")
            # IMPORTANT: Use the ORIGINAL user_query for the re-ranking prompt's context
            rerank_context_str = format_local_results_for_rerank_prompt(local_pages)
            rerank_prompt = construct_rerank_prompt(user_query, rerank_context_str)

            if verbose:
                print("\n--- Re-rank Prompt for Gemini (using original user query for relevance) ---")
                print(rerank_prompt)
                print("--- End of Re-rank Prompt ---")

            print("Asking Gemini to re-rank the local results...")
            reranked_urls = []
            try:
                rerank_response = model.generate_content(rerank_prompt)
                if rerank_response.prompt_feedback and rerank_response.prompt_feedback.block_reason:
                    # ... (error handling for re-rank block)
                    reason = rerank_response.prompt_feedback.block_reason_message or rerank_response.prompt_feedback.block_reason
                    print(f"Re-ranking blocked. Reason: {reason}")
                    context_for_answering = "Re-ranking of local documents was blocked."
                elif rerank_response.parts:
                    if verbose:
                        print("\nGemini's Re-ranked Pages (Raw Output):")
                        print("-" * 20);
                        print(rerank_response.text);
                        print("-" * 20)
                    reranked_urls = parse_reranked_results(rerank_response.text)
                    if not reranked_urls:
                        # ... (handling no URLs parsed)
                        print("Could not parse URLs or no relevant pages identified by re-ranker.")
                        context_for_answering = "Gemini did not identify relevant pages from local search."
                    else:
                        print(f"Successfully extracted {len(reranked_urls)} re-ranked URLs.")
                        print(
                            f"\nRetrieving content for top {min(len(reranked_urls), MAX_PAGES_FOR_ANSWERING)} page(s)...")
                        context_for_answering = get_content_for_answering(reranked_urls, local_pages, verbose=verbose)
                else:
                    # ... (handling no parts in re-rank response)
                    print("No text in re-ranking response and not blocked.")
                    context_for_answering = "Re-ranking process did not yield specific pages."
            except Exception as e:
                print(f"An error during Gemini re-ranking: {e}")
                context_for_answering = "Error during document re-ranking."

        # Consolidated check for context issues
        final_context_message = "No specific new context could be provided for your current query."
        if context_for_answering and not any(msg in context_for_answering for msg in [
            "No specific documents", "No content could be retrieved", "did not identify",
            "did not yield", "was blocked", "Error during"]):
            # Context seems okay
            pass
        else:  # Context is problematic or missing
            if context_for_answering:  # Use the specific error if available
                final_context_message = context_for_answering
            context_for_answering = final_context_message  # Standardize or use specific error

            if verbose:
                print(
                    f"Verbose: Using the following context for Gemini due to issues/lack of content: '{context_for_answering}'")
            else:
                print(f"Info: No new specific context found for this query. Answering based on chat history.")

        print("\nStep 3: Asking Gemini to answer query based on context and chat history...")
        answer_prompt_for_turn = construct_answer_prompt_for_chat_turn(user_query, context_for_answering)

        if verbose:
            print("\n--- Answer Prompt for Current Turn (Context part only) ---")
            print(answer_prompt_for_turn);
            print("--- End of Answer Prompt ---")

        try:
            final_answer_response = chat_session.send_message(answer_prompt_for_turn)
            print("\nGemini's Answer:");
            print("=" * 30)
            if final_answer_response.prompt_feedback and final_answer_response.prompt_feedback.block_reason:
                # ... (handling answer block)
                reason = final_answer_response.prompt_feedback.block_reason_message or final_answer_response.prompt_feedback.block_reason
                print(f"Answering blocked. Reason: {reason}")
            elif final_answer_response.parts:
                print(final_answer_response.text)
            else:
                print("No text in final answer response and not blocked (unexpected).")
            print("=" * 30)
        except Exception as e:
            print(f"An error during Gemini answering: {e}")

    print("\nExiting Gemini Assisted Search & Answer script.")


if __name__ == "__main__":
    main()