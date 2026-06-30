"""
InstaSummary - FastAPI backend
Takes a URL, fetches page content, returns a 5-bullet AI summary via Groq API.
"""

import httpx
import os
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, HttpUrl
from bs4 import BeautifulSoup

app = FastAPI(title="InstaSummary")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Secret path segment for the private stats page — change this to your own secret!
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "letmein123")

# NOTE: Render's free tier has no persistent disk — this file resets to 0
# whenever the app restarts or goes to sleep. Good enough for a rough sense
# of traffic; for accurate long-term stats, a free database (e.g. Supabase)
# would be needed later.
COUNTER_FILE = Path("visit_counter.json")


def _load_counter() -> dict:
    if COUNTER_FILE.exists():
        try:
            return json.loads(COUNTER_FILE.read_text())
        except Exception:
            pass
    return {"visits": 0, "summaries": 0}


def _save_counter(data: dict) -> None:
    COUNTER_FILE.write_text(json.dumps(data))


class SummariseRequest(BaseModel):
    url: HttpUrl


class SummariseResponse(BaseModel):
    title: str
    bullets: list[str]
    source_url: str


def fetch_page_text(url: str) -> tuple[str, str]:
    headers = {"User-Agent": "Mozilla/5.0 (InstaSummary Bot)"}
    try:
        r = httpx.get(url, headers=headers, follow_redirects=True, timeout=10)
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=422, detail=f"Could not fetch URL: {e}")

    soup = BeautifulSoup(r.text, "html.parser")
    title = soup.title.string.strip() if soup.title else "Untitled"

    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    return title, text[:6000]


def summarise_with_groq(title: str, text: str) -> list[str]:
    prompt = f"""You are a world-class summariser. Read the article below and return EXACTLY 5 bullet points.

Rules:
- Each bullet must be one concise sentence (max 20 words).
- Start each bullet with a dash and a space: "- "
- No intro sentence, no conclusion, no markdown beyond the dashes.
- Cover the most important facts, insights, or takeaways.

Article title: {title}

Article text:
{text}
"""

    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 512,
    }

    r = httpx.post(
        GROQ_URL,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )

    if r.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Groq API error: {r.text}")

    raw = r.json()["choices"][0]["message"]["content"].strip()

    bullets = [
        line.lstrip("- ").strip()
        for line in raw.splitlines()
        if line.strip().startswith("- ")
    ]

    if len(bullets) < 2:
        raise HTTPException(
            status_code=500, detail="AI returned an unexpected format. Please retry."
        )

    return bullets[:5]


@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.get("/ads.txt")
def ads_txt():
    return FileResponse("ads.txt", media_type="text/plain")


@app.post("/ping")
def ping():
    """Silently log a visit. Called from the frontend after cookie consent."""
    data = _load_counter()
    data["visits"] += 1
    _save_counter(data)
    return JSONResponse({"ok": True})


@app.get(f"/admin-{ADMIN_SECRET}")
def admin_stats():
    """Private stats page. URL only known to you."""
    data = _load_counter()
    html = f"""
    <html>
    <head><title>InstaSummary — Private Stats</title>
    <style>
      body {{ font-family: monospace; background:#111; color:#eee; padding:3rem; }}
      h1 {{ color:#5b9eff; }}
      .stat {{ font-size:2rem; margin: 1rem 0; }}
      .label {{ color:#888; font-size:.9rem; }}
      .note {{ color:#666; font-size:.8rem; margin-top:2rem; max-width:500px; }}
    </style>
    </head>
    <body>
      <h1>InstaSummary — Private Stats</h1>
      <div class="stat">{data['visits']} <span class="label">visits logged</span></div>
      <div class="stat">{data['summaries']} <span class="label">summaries generated</span></div>
      <p class="note">Note: counts reset whenever the free Render instance restarts/sleeps.
      This is a rough indicator, not exact analytics.</p>
    </body>
    </html>
    """
    return PlainTextResponse(content=html, media_type="text/html")


@app.post("/summarise", response_model=SummariseResponse)
def summarise(req: SummariseRequest):
    url_str = str(req.url)
    title, text = fetch_page_text(url_str)
    bullets = summarise_with_groq(title, text)

    data = _load_counter()
    data["summaries"] += 1
    _save_counter(data)

    return SummariseResponse(title=title, bullets=bullets, source_url=url_str)
