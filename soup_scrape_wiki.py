import requests
from bs4 import BeautifulSoup
import json
from urllib.parse import urljoin
import time

BASE_URL = "https://baldursgate3.wiki.fextralife.com"
START_URL = BASE_URL + "/"

headers = {
    "User-Agent": "Mozilla/5.0"
}

def get_all_article_links():
    print("🔎 Collecting all internal article links...")
    soup = BeautifulSoup(requests.get(START_URL, headers=headers).text, "html.parser")
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/"):
            full_url = urljoin(BASE_URL, href)
            if "baldursgate3.wiki.fextralife.com" in full_url and not any(x in href for x in ["#", "Special", "Category", "File", "Help"]):
                links.add(full_url)
    print(f"✅ Found {len(links)} links to crawl.")
    return list(links)

def extract_content(url):
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")

        title = soup.find("h1")
        content_div = soup.find("div", {"id": "wiki-content"})

        if not content_div:
            print(f"[!] No content div found at {url}")
            return None

        paragraphs = [p.get_text(strip=True) for p in content_div.find_all(["p", "li"])]
        return {
            "url": url,
            "title": title.get_text(strip=True) if title else "Untitled",
            "text": "\n".join(paragraphs)
        }
    except Exception as e:
        print(f"[!] Error at {url}: {e}")
        return None

def main():
    data = []
    links = get_all_article_links()

    for i, url in enumerate(links):
        print(f"Scraping ({i+1}/{len(links)}): {url}")
        result = extract_content(url)
        if result:
            data.append(result)
        time.sleep(1)  # Be respectful to their server

    output_path = "/workspace/bg3_wiki_data.jsonl"
    with open(output_path, "w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item) + "\n")

    print(f"✅ Saved {len(data)} pages to {output_path}")

if __name__ == "__main__":
    main()
