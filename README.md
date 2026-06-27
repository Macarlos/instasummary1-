# InstaSummary — Setup & Run (Windows)

## What you'll need
- Python 3.11+ installed
- An Anthropic API key (get one at https://console.anthropic.com)

---

## 1. Set your API key

Open Command Prompt and run:

```
setx ANTHROPIC_API_KEY "your-key-here"
```

Then **close and reopen** Command Prompt so the variable takes effect.

---

## 2. Install dependencies

Navigate to this folder in Command Prompt:

```
cd path\to\instasummary
pip install -r requirements.txt
```

---

## 3. Run the server

```
uvicorn main:app --reload
```

You'll see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

---

## 4. Open the app

Go to **http://127.0.0.1:8000** in your browser.

Paste any article URL and click **Summarise →**.

---

## API

You can also call it directly:

```
POST http://127.0.0.1:8000/summarise
Content-Type: application/json

{ "url": "https://example.com/article" }
```

Returns:
```json
{
  "title": "Article Title",
  "bullets": ["Point one", "Point two", "Point three", "Point four", "Point five"],
  "source_url": "https://example.com/article"
}
```

---

## Project structure

```
instasummary/
├── main.py            ← FastAPI backend
├── requirements.txt   ← Dependencies
├── README.md          ← This file
└── static/
    └── index.html     ← Frontend UI
```
"# force redeploy" 
