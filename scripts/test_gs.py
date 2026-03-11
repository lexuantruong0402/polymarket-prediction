from googlesearch import search

query = "python"
print("Basic search:")
try:
    for r in search(query, num=3, stop=3, pause=2):
        print(r)
except Exception as e:
    print(f"Error: {e}")

print("\nAdvanced search:")
try:
    for r in search(query, advanced=True, num_results=3):
        print(r.url)
except Exception as e:
    print(f"Error: {e}")
