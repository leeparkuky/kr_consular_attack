import time
import requests
from bs4 import BeautifulSoup
import re
import json
import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://usa-atlanta.mofa.go.kr"
LIST_URL = "https://usa-atlanta.mofa.go.kr/us-atlanta-ko/brd/m_4878/list.do"

# Resolve cache directory from environment or default to ~/.cache/consular
CACHE_DIR = os.environ.get("CONSULAR_CACHE_DIR", os.path.expanduser("~/.cache/consular"))
CACHE_FILE = os.path.join(CACHE_DIR, "atlanta_notices.json")
ATTACHMENTS_DIR = os.path.join(CACHE_DIR, "attachments")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_cache(data):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def scrape_attachments(soup, seq):
    """
    Finds attachment links, downloads them to local disk, and returns the list of metadata.
    """
    attachments = []

    attach_container = soup.find('div', class_='bo_v_file') or soup.find('ul', class_='bo_v_file') or soup.find('div', class_='board_detail')
    if not attach_container:
        attach_container = soup

    links = attach_container.find_all('a')

    for link in links:
        href = link.get('href', '')
        onclick = link.get('onclick', '')

        combined = href + onclick
        match = re.search(r"f_down\('([^']+)'\)", combined)
        if match:
            down_path = match.group(1)
            if down_path.startswith("./"):
                file_url = BASE_URL + "/us-atlanta-ko/brd/m_4878/" + down_path[2:]
            else:
                file_url = BASE_URL + down_path

            filename = link.get_text(strip=True)
            if not filename:
                span = link.find('span')
                if span:
                    filename = span.get_text(strip=True)

            if not filename:
                filename = "unknown_file"

            print(f"    - Found attachment: {filename}")

            # Setup local path
            post_attach_dir = os.path.join(ATTACHMENTS_DIR, str(seq))
            os.makedirs(post_attach_dir, exist_ok=True)
            local_path = os.path.join(post_attach_dir, filename)

            # Download and save the actual file
            if not os.path.exists(local_path):
                r = requests.get(file_url, headers=HEADERS, stream=True)
                if r.status_code == 200:
                    with open(local_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)

            attachments.append({
                "filename": filename,
                "url": file_url,
                "local_path": local_path
            })

            time.sleep(1) # Small delay for each file download

    return attachments

def scrape_post_detail(detail_url, seq):
    response = requests.get(detail_url, headers=HEADERS)
    if response.status_code != 200:
        return "", []

    soup = BeautifulSoup(response.text, 'html.parser')

    content_div = soup.find('div', class_='bo_con') or soup.find('div', class_='view_wrap') or soup.find('div', class_='txa_root')

    text = ""
    if content_div:
        text = content_div.get_text(separator="\n", strip=True)

    attachments = scrape_attachments(soup, seq)

    return text, attachments

def scrape_notice_board(max_pages=100):
    cache = load_cache()
    seen_seqs_this_run = set()

    for page in range(1, max_pages + 1):
        print(f"\n--- Scraping Page {page} ---")

        params = {"page": page}
        response = requests.get(LIST_URL, headers=HEADERS, params=params)

        if response.status_code != 200:
            print(f"Failed to load page {page}")
            break

        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.select("table tbody tr")

        new_posts_found_on_page = 0

        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 5:
                continue

            title_element = cols[1].find('a')
            if not title_element:
                continue

            title = title_element.get_text(strip=True)
            onclick = title_element.get('onclick')
            author = cols[3].get_text(strip=True)
            date = cols[4].get_text(strip=True)

            seq = None
            if onclick:
                match = re.search(r"f_view\('(\d+)'\)", onclick)
                if match:
                    seq = match.group(1)

            if not title or not seq:
                continue

            if seq in seen_seqs_this_run:
                continue

            seen_seqs_this_run.add(seq)
            new_posts_found_on_page += 1

            if seq in cache:
                print(f"Skipping already cached post: {title}")
                continue

            detail_url = f"https://usa-atlanta.mofa.go.kr/us-atlanta-ko/brd/m_4878/view.do?seq={seq}&page={page}"

            print(f"\nFound Post: {title}")
            print(f"Author: {author} | Date: {date}")
            print(f"Scraping content from: {detail_url}")

            post_content, attachments = scrape_post_detail(detail_url, seq)

            cache[seq] = {
                "title": title,
                "author": author,
                "date": date,
                "url": detail_url,
                "content": post_content,
                "attachments": attachments
            }

            save_cache(cache)
            time.sleep(1.5)

        if new_posts_found_on_page == 0:
            print(f"\nNo new posts found on page {page}. Stopping pagination.")
            break

if __name__ == "__main__":
    scrape_notice_board(max_pages=100)
