from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx
import asyncio
import random
import re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

TLDS = [".com", ".io", ".ai", ".co", ".app", ".net"]
PREFIXES = ["get", "my", "the", "go", "try", "use"]
SUFFIXES = ["ly", "ify", "hub", "spot", "labs", "kit"]
VOWELS = set("aeiou")
RDAP_LIMIT = asyncio.Semaphore(5)

def clean_keyword(keyword: str) -> str:
    keyword = keyword.lower().strip()
    keyword = re.sub(r"[^a-z0-9]", "", keyword)
    return keyword or "brand"

def generate_names(keyword: str, count: int):
    names = {keyword}
    for p in PREFIXES:
        names.add(p + keyword)
    for s in SUFFIXES:
        names.add(keyword + s)
    names = list(names)
    random.shuffle(names)
    return names[:count]

def brandability_score(name: str, tld: str) -> int:
    score = 50
    length = len(name)
    if length <= 6:
        score += 25
    elif length <= 10:
        score += 12
    elif length > 14:
        score -= 15
    tld_bonus = {".com": 15, ".ai": 10, ".io": 8, ".app": 5, ".co": 3, ".net": 0}
    score += tld_bonus.get(tld, 0)
    return max(1, min(99, score))

def estimate_value(score: int, name: str, tld: str) -> int:
    base = score * 15
    if tld == ".com":
        base *= 1.6
    elif tld == ".ai":
        base *= 1.4
    return int(base)

async def check_available(client: httpx.AsyncClient, domain: str) -> str:
    async with RDAP_LIMIT:
        try:
            resp = await client.get(f"https://rdap.org/domain/{domain}", timeout=5.0)
            if resp.status_code == 404:
                return "available"
            if resp.status_code == 200:
                return "taken"
            return "unknown"
        except Exception:
            return "unknown"

@app.get("/")
def home():
    return {"app": "DomainFlare AI", "status": "running"}

@app.get("/health")
def health():
    return {"status": "live"}

@app.get("/generate")
async def generate(keyword: str, count: int = 10):
    keyword = clean_keyword(keyword)
    count = max(1, min(count, 20))
    names = generate_names(keyword, count)
    domains = [(name, random.choice(TLDS)) for name in names]
    async with httpx.AsyncClient(follow_redirects=True) as client:
        statuses = await asyncio.gather(
            *[check_available(client, name + tld) for name, tld in domains]
        )
    results = []
    for (name, tld), status in zip(domains, statuses):
        score = brandability_score(name, tld)
        value = estimate_value(score, name, tld)
        results.append({
            "domain": name + tld,
            "available": status,
            "score": score,
            "estimated_value": value,
        })
    results.sort(key=lambda r: r["score"], reverse=True)
    return results
