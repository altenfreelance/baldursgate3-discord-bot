import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
import re
import json # For JSONL output
import os   # For directory creation

# --- Configuration ---
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 MySimpleWikiBot/1.0'
}
REQUEST_DELAY = 1
MAX_URLS_TO_PROCESS_THIS_SESSION = 20000 # Max URLs to attempt to crawl in this run
IGNORE_QUERY_PARAMS = True
IGNORE_FRAGMENTS = True
IGNORED_EXTENSIONS = ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.css', '.js', '.zip', '.xml', '.rss', '.txt', '.ico', '.svg', '.webm', '.mp4', '.mp3']
# --- Output Configuration ---
OUTPUT_FILENAME = "data/raw/bg3_wiki_data.jsonl"

def ensure_dir(file_path):
    """Ensures that the directory for a given file_path exists."""
    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)
        print(f"Created directory: {directory}")

def load_existing_urls(filepath):
    """Loads URLs from an existing JSONL file to avoid re-processing."""
    existing_urls = set()
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        if 'url' in data:
                            existing_urls.add(data['url'])
                    except json.JSONDecodeError:
                        print(f"Warning: Could not decode JSON line in {filepath}: {line.strip()}")
            print(f"Loaded {len(existing_urls)} existing URLs from {filepath}")
        except IOError as e:
            print(f"Error reading existing URLs file {filepath}: {e}")
    return existing_urls

def is_valid_url(url, base_domain):
    """Checks if a URL is valid, within the same domain, and not an ignored type."""
    parsed_url = urlparse(url)
    if not parsed_url.scheme in ['http', 'https']:
        return False
    if parsed_url.netloc != base_domain:
        return False
    if any(parsed_url.path.lower().endswith(ext) for ext in IGNORED_EXTENSIONS):
        return False
    # Avoid crawling special MediaWiki pages if that's the target
    # Example: "Special:", "File:", "Category:", "Template:", "Help:", "MediaWiki:"
    # You might want to customize this list based on the specific wiki structure
    wiki_special_prefixes = ["Special:", "File:", "Category:", "Template:", "Help:", "MediaWiki:", "Talk:"]
    if any(parsed_url.path.split('/')[-1].startswith(prefix) for prefix in wiki_special_prefixes):
        # print(f"  Skipping MediaWiki special page: {url}")
        return False
    return True

def clean_url(url):
    """Cleans a URL by removing fragments and optionally query parameters."""
    parsed = urlparse(url)
    path = parsed.path
    if not path: path = '/'
    query = "" if IGNORE_QUERY_PARAMS else parsed.query
    fragment = "" if IGNORE_FRAGMENTS else parsed.fragment
    if not parsed.netloc: return None
    return parsed._replace(path=path, query=query, fragment=fragment).geturl()

def extract_text_content(soup):
    """Extracts meaningful text content from the page."""
    # Remove script and style elements
    for script_or_style in soup(["script", "style", "noscript", "link", "meta"]):
        script_or_style.decompose()

    # Attempt to find main content area (common IDs/classes, highly site-specific)
    # Examples:
    # main_content = soup.find('main')
    # main_content = soup.find(id='content')
    # main_content = soup.find(class_='mw-parser-output') # Common for MediaWiki
    # If specific main content area is found, use it. Otherwise, use body.
    content_area = soup.find(class_='mw-parser-output') # Example for MediaWiki
    if not content_area:
        content_area = soup.find('main')
    if not content_area:
        content_area = soup.find(id='content') # Common general ID
    if not content_area:
        content_area = soup.body

    if content_area:
        # Remove common non-content elements that might be inside main content
        # This is heuristic and might need adjustment
        for el_to_remove in content_area.find_all(['nav', 'footer', 'aside', 'form', 'header',
                                                    {'class': 'noprint'}, {'class': 'navigation-not-searchable'},
                                                    {'class': 'mw-editsection'}, {'class': 'toc'}, # MediaWiki specific
                                                    {'role': 'navigation'}, {'role': 'search'}, {'role': 'banner'}
                                                    ]):
            el_to_remove.decompose()

        text = content_area.get_text(separator=' ', strip=True)
        text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
        return text
    return ""


def crawl_website(start_url, output_filepath, existing_persisted_urls):
    """
    Crawls a website starting from start_url, extracts title and text,
    and appends data to a JSONL file if the URL hasn't been processed before.
    """
    if not start_url.startswith('http://') and not start_url.startswith('https://'):
        start_url = 'http://' + start_url

    try:
        initial_response = requests.head(start_url, headers=HEADERS, timeout=10, allow_redirects=True)
        initial_response.raise_for_status()
        start_url = initial_response.url
    except requests.exceptions.RequestException as e:
        print(f"Error accessing start URL {start_url}: {e}")
        return 0

    base_domain = urlparse(start_url).netloc
    if not base_domain:
        print(f"Could not determine base domain from {start_url}")
        return 0

    cleaned_start_url = clean_url(start_url)
    if not cleaned_start_url:
        print(f"Could not clean start URL: {start_url}")
        return 0

    urls_to_visit = {cleaned_start_url}
    visited_this_session_urls = set() # Tracks URLs processed in the current crawling session
    new_entries_added = 0

    print(f"Starting crawl on: {start_url}")
    print(f"Base domain: {base_domain}")
    print(f"Max URLs to process this session: {MAX_URLS_TO_PROCESS_THIS_SESSION}")
    print(f"Output file: {output_filepath}")
    print("-" * 30)

    # Open the output file in append mode
    try:
        with open(output_filepath, 'a', encoding='utf-8') as outfile:
            while urls_to_visit and len(visited_this_session_urls) < MAX_URLS_TO_PROCESS_THIS_SESSION:
                current_url = urls_to_visit.pop()

                if current_url in visited_this_session_urls:
                    continue
                visited_this_session_urls.add(current_url)

                print(f"Processing ({len(visited_this_session_urls)}/{MAX_URLS_TO_PROCESS_THIS_SESSION}): {current_url}")

                # Check if URL data already exists in the persisted file
                # This check is crucial for the "don't add if URL already exists" requirement
                if current_url in existing_persisted_urls:
                    print(f"  Skipping data write (already in {output_filepath}): {current_url}")
                    # We still want to parse it for new links if it's a page we might have missed links from before
                    # or if it's a hub page. For simplicity in this version, we'll re-fetch if it was just skipped for writing.
                    # A more advanced setup might avoid re-fetching if content is not needed.
                try:
                    time.sleep(REQUEST_DELAY)
                    response = requests.get(current_url, headers=HEADERS, timeout=15)
                    response.raise_for_status()

                    content_type = response.headers.get('Content-Type', '').lower()
                    if 'text/html' not in content_type:
                        print(f"  Skipping non-HTML content: {content_type}")
                        continue

                    soup = BeautifulSoup(response.content, 'html.parser') # Use response.content for better encoding handling

                    page_title_tag = soup.find('title')
                    page_title = page_title_tag.string.strip() if page_title_tag and page_title_tag.string else ""

                    page_text = extract_text_content(soup)

                    # Only add data if the URL is not already in the output file (checked by existing_persisted_urls)
                    if current_url not in existing_persisted_urls:
                        data_entry = {
                            "url": current_url,
                            "title": page_title,
                            "text": page_text
                        }
                        outfile.write(json.dumps(data_entry) + '\n')
                        outfile.flush() # Ensure data is written to disk
                        existing_persisted_urls.add(current_url) # Add to in-memory set for this session
                        new_entries_added += 1
                        print(f"  Added to {output_filepath}: {current_url} (Title: {page_title[:50]}...)")
                    # else:
                        # Already printed the "Skipping data write" message above

                    # Find and process links on the page
                    for link_tag in soup.find_all('a', href=True):
                        href = link_tag['href']
                        absolute_url = urljoin(current_url, href)
                        cleaned_absolute_url = clean_url(absolute_url)

                        if cleaned_absolute_url and \
                           is_valid_url(cleaned_absolute_url, base_domain) and \
                           cleaned_absolute_url not in visited_this_session_urls and \
                           cleaned_absolute_url not in urls_to_visit:
                            if len(urls_to_visit) < MAX_URLS_TO_PROCESS_THIS_SESSION * 2: # Keep queue size reasonable
                                urls_to_visit.add(cleaned_absolute_url)

                except requests.exceptions.HTTPError as e:
                    print(f"  HTTP Error for {current_url}: {e}")
                except requests.exceptions.ConnectionError as e:
                    print(f"  Connection Error for {current_url}: {e}")
                except requests.exceptions.Timeout:
                    print(f"  Timeout for {current_url}")
                except requests.exceptions.RequestException as e:
                    print(f"  Error fetching {current_url}: {e}")
                except Exception as e:
                    print(f"  An unexpected error occurred while processing {current_url}: {e}")
                    import traceback
                    traceback.print_exc() # For debugging unexpected errors

    except IOError as e:
        print(f"FATAL: Could not open output file {output_filepath} for writing: {e}")
        return 0 # Or raise exception

    return new_entries_added


if __name__ == "__main__":
    target_url = "https://bg3.wiki/"

    print("Generating Site Data for " + target_url)

    if not target_url:
        print("No URL provided. Exiting.")
    else:
        print(f"\nOutput will be saved to: {OUTPUT_FILENAME}")
        ensure_dir(OUTPUT_FILENAME) # Create data/raw/ if it doesn't exist

        # Load URLs that are already in the output file
        persisted_urls = load_existing_urls(OUTPUT_FILENAME)

        print("\nStarting crawler...\n")
        newly_added_count = crawl_website(target_url, OUTPUT_FILENAME, persisted_urls)

        print("\n--- Crawl Finished ---")
        if newly_added_count > 0:
            print(f"Successfully added {newly_added_count} new entries to {OUTPUT_FILENAME}.")
        else:
            print(f"No new entries were added to {OUTPUT_FILENAME} in this session.")
        print(f"Total unique URLs in {OUTPUT_FILENAME} (including previous): {len(persisted_urls)}")