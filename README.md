# Docent

*An AI reading-room attendant for your documents.*

Drop in a scan or a PDF. Docent reads it, writes the catalog card — title,
one-line summary, tags, document type — and files it so you can find it
again by searching, or by browsing the shelf.

It's a small, single-purpose alternative to running a full document
management platform just to get AI-tagged, searchable scans. No cloud
account, no separate services to stand up, one SQLite file as the database.

![Docent library view](materials/screenshot-library.png)

## Why this exists

Tools like Paperless-ngx are excellent, but they're a whole platform —
consumption folders, a task queue, a separate web server, a Postgres/Redis
stack — built to be the permanent home for your entire document archive.
Sometimes you just want the one feature: **hand it a document, get back a
title, a summary, and tags, searchable later.** Docent is that one feature,
built as a complete, standalone thing rather than a plugin bolted onto a
bigger system.

## What it actually does

- **Reads the file.** Native-text PDFs are parsed directly; scanned PDFs and
  images go through Tesseract OCR. Mixed documents (some real pages, some
  scanned pages) are handled page-by-page.
- **Writes the catalog card.** An LLM call (any OpenAI-compatible endpoint —
  OpenAI, Azure OpenAI, or a local model via Ollama/LM Studio) generates the
  title, summary, tags, and document type.
- **Works with zero setup.** No API key configured? Docent falls back to a
  local heuristic reader (keyword frequency + rule-based type detection) so
  the app is fully functional offline, out of the box. Add a key later and
  every document can be re-read with one click.
- **Files it.** One SQLite table. Search by title, tag, or full extracted
  text. Filter by document type.

That's the whole feature set. No user accounts, no folders, no sharing, no
workflow rules — those are the parts of a "document intelligence platform"
that make it a multi-week build. This is the part that makes it useful.

## Screenshots

**The shelf** — every document Docent has read, filterable by type:

![Library view with three catalogued documents](materials/screenshot-library.png)

**A catalog card** — the AI-written summary, tags, and the full extracted
text underneath it:

![Document detail view](materials/screenshot-detail.png)

*(Both screenshots are of the actual running app — an invoice, a lease
agreement, and a quarterly report were fed through the real OCR + cataloging
pipeline to produce them.)*

## Running it

```bash
git clone <this-repo>
cd docent
pip install -r requirements.txt

# System dependencies (not pip-installable):
#   tesseract-ocr   — OCR engine
#   poppler-utils   — provides pdftoppm, for rasterizing scanned PDF pages

python app.py
```

Open `http://localhost:5000`. Drop in a PDF or image.

### Turning on the LLM reader (optional)

```bash
export DOCENT_LLM_API_KEY=sk-...
export DOCENT_LLM_MODEL=gpt-4o-mini          # any chat-completions model
export DOCENT_LLM_BASE_URL=https://api.openai.com/v1   # or a local server
```

Without these three lines, Docent uses its local heuristic reader — real
titles, real tags, real type detection, just not LLM-quality prose.

## How it's built

```
app.py              Flask routes — upload, library, document detail, retag, delete
docent/
  ocr.py             pypdf for native PDF text, Tesseract + pdftoppm for scans/images
  enrich.py           LLM cataloging with an offline heuristic fallback
  storage.py           SQLite, no ORM — one table, five queries
templates/            Server-rendered Jinja2, no build step
static/style.css       The whole visual identity, one file
```

Five modules, one dependency-light `requirements.txt`, no background job
queue, no separate microservice for OCR. It's meant to be readable end to
end in one sitting — that's the point of building it this way rather than
adopting the architecture of a bigger platform.

## License

MIT
