# gemini_rag_core.py
import google.generativeai as genai
import re
from find_matching_wiki_pages import search_documents  # Ensure this is accessible

# --- Constants ---
MAX_KEYWORDS_PER_PAGE_IN_PROMPT = 7
MAX_PAGES_FOR_ANSWERING = 3
NUM_HISTORY_TURNS_FOR_GUIDANCE = 4
# KNOWLEDGE_BASE_TOPIC can be passed to process_query or defined here if static
# For simplicity, let's assume it's passed if it varies, or static if not.
DEFAULT_KNOWLEDGE_BASE_TOPIC = "Baldur's Gate 3 game information"


# --- Helper function to format chat history ---
def format_chat_history_snippet(history: list, num_turns: int) -> str:
    if not history:
        return "No prior conversation history."
    snippet = "Recent Conversation Snippet:\n"
    relevant_history = history[-num_turns:]
    for message_content in relevant_history:
        role = getattr(message_content, 'role', 'unknown').capitalize()
        text_parts_collected = []
        if hasattr(message_content, 'parts') and isinstance(message_content.parts, list):
            for part in message_content.parts:
                if hasattr(part, 'text'):
                    text_parts_collected.append(part.text)
        text = " ".join(text_parts_collected).strip() if text_parts_collected else "[empty or non-text parts]"
        snippet += f"- {role}: {text}\n"
    return snippet


# --- RAG Pipeline Functions ---
def format_local_results_for_rerank_prompt(pages: list[dict]) -> str:
    if not pages:
        return "No specific pages found."
    formatted_string = "Locally found pages:\n\n"
    for i, page in enumerate(pages, 1):
        formatted_string += f"{i}. Title: {page.get('title', 'N/A')}\n"
        formatted_string += f"   URL: {page.get('url', 'N/A')}\n"
        doc_keywords_with_weights = page.get('keywords', [])
        if doc_keywords_with_weights:
            kw_list = []
            for kw_entry in doc_keywords_with_weights[:MAX_KEYWORDS_PER_PAGE_IN_PROMPT]:
                if isinstance(kw_entry, (list, tuple)) and len(kw_entry) == 2:
                    kw_list.append(f"{str(kw_entry[0])} (w: {float(kw_entry[1]):.2f})")
                elif isinstance(kw_entry, str):
                    kw_list.append(kw_entry)
            if kw_list:
                formatted_string += f"   Keywords: {', '.join(kw_list)}\n"
        formatted_string += "\n"
    return formatted_string


def construct_rerank_prompt(original_user_query: str, local_search_results_str: str) -> str:
    return (f"Original User Query: \"{original_user_query}\"\n\n"
            f"Local search results:\n{local_search_results_str}\n"
            "Task: Re-rank these pages by relevance to the Original User Query.\n"
            "Output: Numbered list of 'Title' and 'URL' for top 10.\n"
            "Example:\n1. Title: T1\n   URL: U1")


def parse_reranked_results(gemini_response_text: str) -> list[str]:
    return re.findall(r"^\s*URL:\s*(https?://[^\s]+)", gemini_response_text, re.MULTILINE | re.IGNORECASE)


def get_content_for_answering(reranked_urls: list[str], all_local_pages: list[dict], verbose: bool = False) -> str:
    content = ""
    found_count = 0
    if not reranked_urls: return "No documents identified as relevant by re-ranking."
    for url in reranked_urls[:MAX_PAGES_FOR_ANSWERING]:
        doc = next((d for d in all_local_pages if d.get('url') == url), None)
        if doc:
            found_count += 1
            text = doc.get('text', '')
            title = doc.get('title', 'N/A')
            content += f"\n\n--- Context from {title} ({url}) ---\n{text if text else 'No text content.'}"
        elif verbose:
            print(f"CoreRAG Verbose: Doc for URL {url} not found in local_pages.")
    return content if found_count else "No content retrieved for re-ranked pages."


def construct_answer_prompt_for_chat_turn(current_user_query: str, context_text: str) -> str:
    return (f"User's current query: \"{current_user_query}\"\n\n"
            f"Context from knowledge base:\n--- START ---\n{context_text}\n--- END ---\n\n"
            "Task: Given ongoing chat & new context, answer current query. Prioritize new context. If info lacking, say so. No external knowledge.")


def construct_llm_search_guidance_prompt(user_query: str, history_snippet: str, kb_topic: str) -> str:
    return (f"User's query: \"{user_query}\"\nKB search about \"{kb_topic}\" failed.\n{history_snippet}\n"
            "Based on query & chat, suggest an improved search query (2-5 words) for my KB. Output ONLY the query string.\n"
            "Example: if user asked 'which one?' after 'Barbarian subclasses', suggest 'Barbarian subclass comparison'.")


# --- Main Processing Function for the RAG Core ---
def process_query_with_rag_chat(
        user_query: str,
        chat_session: genai.ChatSession,  # Pass the user's specific chat session
        model: genai.GenerativeModel,
        knowledge_base_topic: str = DEFAULT_KNOWLEDGE_BASE_TOPIC,  # Allow overriding
        verbose: bool = False
) -> str:
    """
    Processes a single user query using the RAG pipeline and the provided chat session.
    """
    if verbose: print(f"\nCoreRAG Verbose: Processing query: '{user_query}'")

    # Stage 1: Initial local search
    if verbose: print("CoreRAG Verbose: Step 1: Initial local search...")
    local_pages = search_documents(user_query)

    # Stage 1b: LLM-Guided Search Augmentation
    if not local_pages:
        if verbose: print("CoreRAG Verbose: Initial search failed. Attempting LLM-guided search.")
        history_for_guidance = chat_session.history or []
        formatted_hist_snippet = format_chat_history_snippet(history_for_guidance, NUM_HISTORY_TURNS_FOR_GUIDANCE)
        guidance_prompt_str = construct_llm_search_guidance_prompt(user_query, formatted_hist_snippet,
                                                                   knowledge_base_topic)
        if verbose: print(f"CoreRAG Verbose: --- LLM Guidance Prompt ---\n{guidance_prompt_str}\n--- End ---")
        try:
            guidance_response = model.generate_content(guidance_prompt_str)
            suggested_query = guidance_response.text.strip() if guidance_response.parts else ""
            if guidance_response.prompt_feedback and guidance_response.prompt_feedback.block_reason:
                if verbose: print(
                    f"CoreRAG Verbose: LLM guidance blocked: {guidance_response.prompt_feedback.block_reason_message or guidance_response.prompt_feedback.block_reason}")
            elif suggested_query:
                if verbose: print(f"CoreRAG Verbose: LLM suggested query: '{suggested_query}'")
                local_pages = search_documents(suggested_query)
                if verbose: print(f"CoreRAG Verbose: Found {len(local_pages)} pages after LLM guidance.")
            elif verbose:
                print("CoreRAG Verbose: LLM guidance yielded no usable query.")
        except Exception as e:
            if verbose: print(f"CoreRAG Verbose: Error in LLM-guided search: {e}")

    # Stage 2: Re-ranking
    context_for_answering = "No specific documents found in the knowledge base for your query."
    if local_pages:
        if verbose: print(f"CoreRAG Verbose: Step 2: Re-ranking {len(local_pages)} pages...")
        rerank_context_str = format_local_results_for_rerank_prompt(local_pages)
        rerank_prompt = construct_rerank_prompt(user_query, rerank_context_str)  # Use original query
        if verbose: print(f"CoreRAG Verbose: --- Re-rank Prompt ---\n{rerank_prompt}\n--- End ---")
        try:
            rerank_response = model.generate_content(rerank_prompt)
            reranked_urls = []
            if rerank_response.prompt_feedback and rerank_response.prompt_feedback.block_reason:
                if verbose: print(
                    f"CoreRAG Verbose: Re-ranking blocked: {rerank_response.prompt_feedback.block_reason_message or rerank_response.prompt_feedback.block_reason}")
                context_for_answering = "Re-ranking of local documents was blocked."
            elif rerank_response.parts:
                if verbose: print(
                    f"CoreRAG Verbose: --- Gemini's Re-ranked (Raw) ---\n{rerank_response.text}\n--- End ---")
                reranked_urls = parse_reranked_results(rerank_response.text)
                if reranked_urls:
                    context_for_answering = get_content_for_answering(reranked_urls, local_pages, verbose=verbose)
                else:
                    context_for_answering = "Re-ranking did not identify relevant pages."
            else:
                context_for_answering = "Re-ranking process yielded no specific pages."
        except Exception as e:
            if verbose: print(f"CoreRAG Verbose: Error in re-ranking: {e}")
            context_for_answering = "Error during document re-ranking."
    elif verbose:
        print("CoreRAG Verbose: No local pages to re-rank.")

    # Stage 3: Gemini Answering
    if verbose: print("CoreRAG Verbose: Step 3: Asking Gemini to answer...")
    answer_prompt_for_turn = construct_answer_prompt_for_chat_turn(user_query, context_for_answering)
    if verbose: print(f"CoreRAG Verbose: --- Answer Prompt (Context) ---\n{answer_prompt_for_turn}\n--- End ---")

    try:
        final_answer_response = chat_session.send_message(answer_prompt_for_turn)  # Uses the passed chat_session
        if final_answer_response.prompt_feedback and final_answer_response.prompt_feedback.block_reason:
            return f"My response was blocked. Reason: {final_answer_response.prompt_feedback.block_reason_message or final_answer_response.prompt_feedback.block_reason}"
        elif final_answer_response.parts:
            return final_answer_response.text
        return "I received an empty response and wasn't blocked. Not sure how to reply."
    except Exception as e:
        if verbose: print(f"CoreRAG Verbose: Error in final answering: {e}")
        return f"An error occurred while formulating an answer: {e}"

# Optional: A function to initialize the Gemini model if you want it self-contained
# but it's often better to initialize in the main application (bot) once.
# For now, the model will be passed into process_query_with_rag_chat.