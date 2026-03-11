import googlesearch.user_agents
googlesearch.user_agents.get_useragent = lambda: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"

from googlesearch import _req
resp = _req("SpaceX launch Starship Mars 2026", 10, "en", 0, None, 5, "active", None, None)
with open("google_patch.html", "w") as f:
    f.write(resp.text)
