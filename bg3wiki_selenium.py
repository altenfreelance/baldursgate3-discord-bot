import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import os

# Setup headless Chrome
options = Options()
options.add_argument("--headless=new")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(options=options)

# Define output
output_file = "bg3_wiki_data.jsonl"
visited = set()
to_visit = set(["https://bg3.wiki/"])
saved_pages = 0

# Helper function
def get_links_and_content(url):
    driver.get(url)
    time.sleep(2)  # wait for JS
    soup = BeautifulSoup(driver.page_source, "html.parser")

    # Extract main article content
    content = soup.find("div", class_="mw-parser-output")
    title = soup.find("h1")
    if content and title:
        data = {
            "url": url,
            "title": title.get_text(strip=True),
            "text": content.get_text(separator="\n", strip=True),
        }
        with open(output_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(data) + "\n")
        global saved_pages
        saved_pages += 1
        print(f"✅ Saved: {title.get_text(strip=True)}")

    # Find internal wiki links
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/wiki/") and ":" not in href and "#" not in href:
            full_url = "https://bg3.wiki" + href
            if full_url not in visited:
                to_visit.add(full_url)

# Crawl
while to_visit and saved_pages < 1000:
    current = to_visit.pop()
    if current in visited:
        continue
    print(f"🕷️ Scraping: {current}")
    try:
        get_links_and_content(current)
    except Exception as e:
        print(f"[!] Failed to scrape {current}: {e}")
    visited.add(current)

driver.quit()
print(f"\n🎉 Scraping complete! {saved_pages} pages saved to {output_file}")
