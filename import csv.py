import csv
import time
import urllib.parse
import requests
from bs4 import BeautifulSoup

# Define your search query
query = 'site:linkedin.com/in/ ("Fire and Rescue" OR "Fire Brigade") ("Head of IT" OR "Head of ICT" OR "Head of Technology" OR "Head of Data" OR "ICT Manager") "United Kingdom"'
encoded_query = urllib.parse.quote(query)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

results = []

# Fetch first 3 pages (approx 30 results)
for page in range(0, 3):
    start = page * 10
    url = f"https://www.google.com/search?q={encoded_query}&start={start}"
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print("Rate limit reached or blocked by Google. Try using a SERP API or Chrome extension.")
        break
        
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Parse organic search result cards
    for g in soup.find_all("div", class_="tF2Cxc"):
        title_el = g.find("h3")
        link_el = g.find("a")
        snippet_el = g.find("div", class_="VwiC3b")

        if title_el and link_el:
            raw_title = title_el.get_text()
            link = link_el.get("href")
            snippet = snippet_el.get_text() if snippet_el else ""

            # Google LinkedIn titles usually follow: "Name - Job Title - Company | LinkedIn"
            parts = [p.strip() for p in raw_title.replace(" | LinkedIn", "").split(" - ")]
            name = parts[0] if len(parts) > 0 else ""
            headline = parts[1] if len(parts) > 1 else ""
            company = parts[2] if len(parts) > 2 else ""

            results.append({
                "Name": name,
                "Headline / Role": headline,
                "Identified Organisation": company,
                "LinkedIn Profile URL": link,
                "Snippet Context": snippet
            })
            
    time.sleep(2)  # Short pause between pages to prevent rapid requests

# Save directly to CSV
with open("fire_brigade_it_leads.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["Name", "Headline / Role", "Identified Organisation", "LinkedIn Profile URL", "Snippet Context"])
    writer.writeheader()
    writer.writerows(results)

print(f"Extraction complete! Saved {len(results)} contacts to fire_brigade_it_leads.csv")