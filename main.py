"""
InstaSummary - FastAPI backend
Takes a URL, fetches page content, returns a 5-bullet AI summary via Google Gemini Flash API.
"""

import httpx
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl
from bs4 import BeautifulSoup

app = FastAPI(title="InstaSummary")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


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


def summarise_with_gemini(title: str, text: str) -> list[str]:
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
        "contents": [{"parts": [{"text": prompt}]}]
    }

    r = httpx.post(
        GEMINI_URL,
        params={"key": GEMINI_API_KEY},
        json=payload,
        timeout=30
    )

    if r.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Gemini API error: {r.text}")

    raw = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

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


@app.post("/summarise", response_model=SummariseResponse)
def summarise(req: SummariseRequest):
    url_str = str(req.url)
    title, text = fetch_page_text(url_str)
    bullets = summarise_with_gemini(title, text)
    return SummariseResponse(title=title, bullets=bullets, source_url=url_str)
