"""
Docent's "reading" step: turns raw OCR text into a catalog card
(title, one-line summary, tags, document type).

Two modes, same output shape:

  - LLM mode: used automatically if DOCENT_LLM_API_KEY is set. Speaks
    the standard OpenAI-compatible /chat/completions shape, so it
    works against OpenAI, Azure OpenAI, or a local server like Ollama
    / LM Studio — just point DOCENT_LLM_BASE_URL at it.

  - Local mode: a small, dependency-free heuristic (word frequency +
    keyword rules) that ships as the default. It's not going to
    write poetry, but it means Docent works fully offline and gives
    every document a real card, out of the box, before you've wired
    up any API key.

Swap in a different LLM by editing _catalog_with_llm — everything
else in the app only depends on the four-field dict this returns.
"""
import os
import re
from collections import Counter

import requests

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for",
    "with", "is", "are", "was", "were", "be", "been", "this", "that",
    "these", "those", "it", "its", "as", "at", "by", "from", "your",
    "you", "we", "our", "will", "shall", "not", "no", "if", "then",
    "than", "so", "such", "into", "about", "have", "has", "had", "all",
    "any", "can", "may", "please", "date", "page",
}

TYPE_RULES = [
    ("invoice", ["invoice", "amount due", "bill to", "invoice number"]),
    ("receipt", ["receipt", "total paid", "change due", "cashier"]),
    ("contract", ["agreement", "hereinafter", "party of the", "terms and conditions", "signature"]),
    ("letter", ["dear ", "sincerely", "regards,", "to whom it may concern"]),
    ("resume", ["experience", "education", "skills", "curriculum vitae"]),
    ("report", ["executive summary", "findings", "methodology", "appendix"]),
    ("form", ["please check one", "signature:", "date of birth", "applicant"]),
]


def catalog(raw_text: str, original_filename: str = "") -> dict:
    text = (raw_text or "").strip()
    if not text:
        return {
            "title": _title_from_filename(original_filename),
            "summary": "Docent couldn't find any readable text in this file.",
            "tags": ["unreadable"],
            "doc_type": "unknown",
            "source": "empty",
        }

    if os.environ.get("DOCENT_LLM_API_KEY"):
        try:
            return _catalog_with_llm(text)
        except Exception:
            pass  # fall through to local mode — Docent should never hard-fail on a bad API call

    return _catalog_local(text, original_filename)


# ---------------------------------------------------------------- LLM mode

def _catalog_with_llm(text: str) -> dict:
    base_url = os.environ.get("DOCENT_LLM_BASE_URL", "https://api.openai.com/v1")
    model = os.environ.get("DOCENT_LLM_MODEL", "gpt-4o-mini")
    api_key = os.environ["DOCENT_LLM_API_KEY"]

    prompt = (
        "You are a library cataloger. Read the document text and return strict JSON "
        "with keys: title (short, specific), summary (one sentence), "
        "tags (3-6 lowercase keywords, no hashtags), doc_type (one word: "
        "invoice, receipt, contract, letter, resume, report, form, or other).\n\n"
        f"DOCUMENT TEXT:\n{text[:6000]}"
    )

    response = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        },
        timeout=30,
    )
    response.raise_for_status()
    import json
    content = response.json()["choices"][0]["message"]["content"]
    parsed = json.loads(content)

    return {
        "title": parsed.get("title") or "Untitled document",
        "summary": parsed.get("summary") or "",
        "tags": [t.lower() for t in parsed.get("tags", [])][:6],
        "doc_type": (parsed.get("doc_type") or "other").lower(),
        "source": f"llm:{model}",
    }


# -------------------------------------------------------------- local mode

def _catalog_local(text: str, original_filename: str) -> dict:
    lowered = text.lower()

    doc_type = "other"
    for label, keywords in TYPE_RULES:
        if any(kw in lowered for kw in keywords):
            doc_type = label
            break

    title = _first_meaningful_line(text) or _title_from_filename(original_filename)
    summary = _first_sentences(text, max_sentences=2, max_chars=220)
    tags = _keywords(text, doc_type, limit=5)

    return {
        "title": title,
        "summary": summary,
        "tags": tags,
        "doc_type": doc_type,
        "source": "local-heuristic",
    }


def _first_meaningful_line(text: str) -> str:
    for line in text.splitlines():
        clean = line.strip(" -_=*#\t")
        if 4 <= len(clean) <= 90:
            return clean
    return ""


def _first_sentences(text: str, max_sentences=2, max_chars=220) -> str:
    flat = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[.!?])\s+", flat)
    summary = " ".join(sentences[:max_sentences])
    if len(summary) > max_chars:
        summary = summary[:max_chars].rsplit(" ", 1)[0] + "…"
    return summary or "No summary available."


def _keywords(text: str, doc_type: str, limit=5) -> list:
    words = re.findall(r"[a-zA-Z]{4,}", text.lower())
    counts = Counter(w for w in words if w not in STOPWORDS)
    top = [word for word, _ in counts.most_common(limit)]
    if doc_type != "other" and doc_type not in top:
        top = [doc_type] + top[: limit - 1]
    return top or ["uncategorized"]


def _title_from_filename(filename: str) -> str:
    stem = re.sub(r"[_\-]+", " ", filename.rsplit(".", 1)[0]) if filename else "Untitled document"
    return stem.strip().title() or "Untitled document"
