from googlesearch import _req
from bs4 import BeautifulSoup

resp = _req("SpaceX launch Starship Mars 2026", 10, "en", 0, None, 5, "active", None, None)
with open("google.html", "w") as f:
    f.write(resp.text)
soup = BeautifulSoup(resp.text, "html.parser")
print(f"ezO2md count: {len(soup.find_all('div', class_='ezO2md'))}")
print(f"Any div count: {len(soup.find_all('div'))}")
for a in soup.find_all('a')[:5]:
    print(a.get('href'))
