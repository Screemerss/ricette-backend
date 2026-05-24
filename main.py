from fastapi import FastAPI, Request
import requests, os, json, time
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
CACHE_FILE = "cache.json"
RATE_LIMIT_SECONDS = 10
USER_LIMIT_PER_DAY = 3

cache = {}
user_requests = {}

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_cache():
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)

cache = load_cache()

@app.post("/generate")
async def generate_recipe(request: Request):
    data = await request.json()
    prompt = data.get("prompt")
    user_id = data.get("user_id", "anon")

    now = time.time()
    last_request = user_requests.get(user_id, 0)
    if now - last_request < RATE_LIMIT_SECONDS:
        return {"error": "Troppo veloce! Aspetta qualche secondo."}
    user_requests[user_id] = now

    today = time.strftime("%Y-%m-%d")
    user_count = cache.get("user_count", {}).get(user_id, {}).get(today, 0)
    if user_count >= USER_LIMIT_PER_DAY:
        return {"error": "Hai raggiunto il limite giornaliero di ricette."}

    if prompt in cache.get("recipes", {}):
        return {"cached": True, "recipe": cache["recipes"][prompt]}

    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": "Sei un esperto chef italiano. Genera una ricetta completa e dettagliata."},
            {"role": "user", "content": prompt}
        ]
    }

    response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
    result = response.json()

    recipe_text = result["choices"][0]["message"]["content"]

    cache.setdefault("recipes", {})[prompt] = recipe_text
    cache.setdefault("user_count", {}).setdefault(user_id, {})[today] = user_count + 1
    save_cache()

    return {"cached": False, "recipe": recipe_text}
