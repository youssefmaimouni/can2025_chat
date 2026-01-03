import requests
import json

URL = "http://127.0.0.1:5000/api/ask"

with open("test_queries.json", "r", encoding="utf-8") as f:
    tests = json.load(f)

for category, questions in tests.items():
    print(f"\n=== {category.upper()} ===")
    for q in questions:
        response = requests.post(
            URL,
            json={"question": q}
        )
        data = response.json()
        print("\nQ:", q)
        print("A:", data.get("answer", "No answer"))
