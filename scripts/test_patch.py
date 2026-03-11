import googlesearch.user_agents
googlesearch.user_agents.get_useragent = lambda: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

from googlesearch import search
query = "SpaceX launch Starship Mars 2026"
results = list(search(query, num_results=5, advanced=True))
print(f"Got {len(results)} results")
for r in results:
    print(r.title)
