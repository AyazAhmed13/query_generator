import requests
import os
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("OPENROUTER_API_KEY")
headers = {
    "Authorization": f"Bearer {api_key}",
    "HTTP-Referer": "http://localhost",
    "Content-Type": "application/json"
}
data = {
    "model": "deepseek/deepseek-r1-distill-llama-70b:free",
    "messages": [{"role": "user", "content": "Hello! What is 2 + 2?"}]
}
r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
print(r.status_code, r.text)
