import httpx
from bs4 import BeautifulSoup

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}

resp = httpx.get("https://www.google.com/search?q=SpaceX+launch+Starship+Mars+2026&hl=en", headers=headers, follow_redirects=True)
with open("google_httpx.html", "w") as f:
    f.write(resp.text)

soup = BeautifulSoup(resp.text, "html.parser")
print(f"Any div count: {len(soup.find_all('div'))}")

# Look for standard search results
results = soup.select("div.g")
print(f"Standard results div.g count: {len(results)}")
for r in results[:2]:
    a = r.find("a")
    link = a["href"] if a else ""
    h3 = r.find("h3")
    title = h3.text if h3 else ""
    print(f"Title: {title}\nLink: {link}\n")
