from duckduckgo_search import DDGS

def test_ddg():
    with DDGS() as ddgs:
        results = list(ddgs.text("SpaceX launch Starship Mars 2026", max_results=5))
        for r in results:
            print(f"Title: {r['title']}")
            print(f"URL: {r['href']}")
            print(f"Body: {r['body']}")
            print("---")

if __name__ == "__main__":
    test_ddg()
