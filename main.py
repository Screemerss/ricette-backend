from fastapi import FastAPI
from pydantic import BaseModel
import requests, os, json, time
from dotenv import load_dotenv

# Carica variabili d'ambiente (su Railway usa quelle in "Variables")
load_dotenv()

app = FastAPI()

# Legge la chiave Groq da Railway
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Percorso sicuro per Railway (scrivibile)
CACHE_FILE = "/tmp/cache.json"

RATE_LIMIT_SECONDS = 10
USER_LIMIT_PER_DAY = 3

cache = {}
user_requests = {}

# ✅ Modello Pydantic per Swagger
class RecipeRequest(BaseModel):
    prompt: str
    user_id: str = "anon"

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_cache():
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f)
    except:
        pass  # Railway potrebbe non permettere scrittura, ma non blocchiamo il server

cache = load_cache()

@app.post("/generate")
async def generate_recipe(data: RecipeRequest):
    prompt = data.prompt
    user_id = data.user_id

    # Rate limit
    now = time.time()
    last_request = user_requests.get(user_id, 0)
    if now - last_request < RATE_LIMIT_SECONDS:
        return {"error": "Troppo veloce! Aspetta qualche secondo."}
    user_requests[user_id] = now

    # Limite giornaliero
    today = time.strftime("%Y-%m-%d")
    user_count = cache.get("user_count", {}).get(user_id, {}).get(today, 0)
    if user_count >= USER_LIMIT_PER_DAY:
        return {"error": "Hai raggiunto il limite giornaliero di ricette."}

    # Cache ricette
    if prompt in cache.get("recipes", {}):
        return {"cached": True, "recipe": cache["recipes"][prompt]}

    # Controllo chiave API
    if not GROQ_API_KEY:
        return {"error": "Server: GROQ_API_KEY mancante."}

    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": "Sei un esperto chef italiano. Genera una ricetta completa e dettagliata."},
            {"role": "user", "content": prompt}
        ]
    }

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers,
        json=payload
    )

    result = response.json()

    # Estrai testo ricetta
    recipe_text = result["choices"][0]["message"]["content"]

    # Salva in cache
    cache.setdefault("recipes", {})[prompt] = recipe_text
    cache.setdefault("user_count", {}).setdefault(user_id, {})[today] = user_count + 1
    save_cache()

    return {"cached": False, "recipe": recipe_text}

# ✅ Endpoint di test per verificare che il server sia online
@app.get("/status")
def status():
    return {"status": "Server online e pronto!"}
