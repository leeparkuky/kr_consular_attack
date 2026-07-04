import time
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import re

# Initialize your LLM client (adjust based on your provider)
client = OpenAI(api_key="YOUR_OPENAI_API_KEY")

BASE_URL = "https://usa-atlanta.mofa.go.kr"
# The exact URL structure for the notice board list
LIST_URL = "https://usa-atlanta.mofa.go.kr/us-atlanta-ko/brd/m_4878/list.do"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def ask_llm_about_post(title, content):
    """
    Sends the scraped post text to the LLM to process.
    """
    prompt = f"""
    You are an assistant analyzing official embassy notices.
    Review the following post and determine if it requires urgent action from citizens (e.g., safety warnings, office hour changes).

    Title: {title}
    Content: {content}

    Provide a brief 1-sentence summary and classify it as 'Urgent' or 'Routine'.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"LLM Processing Error: {e}"

def scrape_post_content(detail_url):
    """
    Navigates to an individual post's page and extracts its full body text.
    """
    response = requests.get(detail_url, headers=HEADERS)
    if response.status_code != 200:
        return ""

    soup = BeautifulSoup(response.text, 'html.parser')

    # The main text content container on MOFA sites is usually inside a div with class 'bo_con'
    # Fallback to general text container if class differs
    content_div = soup.find('div', class_='bo_con') or soup.find('div', class_='view_wrap') or soup.find('div', class_='txa_root')

    if content_div:
        return content_div.get_text(separator="\n", strip=True)
    return "Could not extract body content."

def scrape_notice_board(max_pages=2):
    """
    Scrapes the list page, handles pagination, and extracts post links.
    """
    for page in range(1, max_pages + 1):
        print(f"\n--- Scraping Page {page} ---")

        # The site tracks pages using the 'page' query parameter
        params = {"page": page}
        response = requests.get(LIST_URL, headers=HEADERS, params=params)

        if response.status_code != 200:
            print(f"Failed to load page {page}")
            break

        soup = BeautifulSoup(response.text, 'html.parser')

        # Find the board table rows
        # The list items are wrapped inside standard table rows (tr) within the table body
        rows = soup.select("table tbody tr")

        for row in rows:
            # Extract the title link element
            title_element = row.select_one("td.al a") or row.select_one("td a")
            if not title_element:
                continue

            title = title_element.get_text(strip=True)
            onclick = title_element.get('onclick')

            # The site uses onclick="f_view('seq_number');"
            seq = None
            if onclick:
                match = re.search(r"f_view\('(\d+)'\)", onclick)
                if match:
                    seq = match.group(1)

            # Skip empty entries or pagination elements without seq
            if not title or not seq:
                continue

            # Build absolute URL for the detail page
            detail_url = f"https://usa-atlanta.mofa.go.kr/us-atlanta-ko/brd/m_4878/view.do?seq={seq}&page={page}"

            print(f"\nFound Post: {title}")
            print(f"Scraping content from: {detail_url}")

            # 1. Scrape individual post text
            post_content = scrape_post_content(detail_url)

            # 2. Pass data to the LLM
            print("Sending to LLM...")
            llm_decision = ask_llm_about_post(title, post_content)

            print(f"LLM Result:\n{llm_decision}")

            # Polite delay to avoid stressing the embassy server
            time.sleep(1.5)

if __name__ == "__main__":
    # Adjust max_pages to scrape further back in time
    scrape_notice_board(max_pages=1)
