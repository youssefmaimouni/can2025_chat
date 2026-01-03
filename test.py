import requests
import os
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("OPENROUTER_API_KEY")
url = "https://openrouter.ai/api/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {key}",
    "Content-Type": "application/json"
}

payload = {
    "model": "mistralai/mistral-7b-instruct:free",
    "messages": [{"role": "user", "content": "Hello"}]
}

print(f"Test de l'URL: {url}")
print(f"Clé trouvée (tronquée): {key[:10]}...")

try:
    res = requests.post(url, headers=headers, json=payload)
    print(f"Code de statut: {res.status_code}")
    print(f"Réponse: {res.text}")
except Exception as e:
    print(f"Erreur: {e}")