from pathlib import Path

import anthropic
import chromadb
from pypdf import PdfReader

MODEL = "claude-opus-4-8"
PDF_PATH = Path(__file__).parent / "Zombie_Plan.pdf"
CHROMA_PATH = str(Path(__file__).parent / "chroma_db")
COLLECTION = "zombie_plan"

RAG_SYSTEM = (
    "You are SURVIVAL-AI, a calm, authoritative advisor during a fictional zombie "
    "apocalypse. Answer the survivor's question using the provided excerpts from the "
    "official Zombie Plan as your primary source of truth, and factor in the live event "
    "feed when relevant. Be concrete and prioritized: lead with the single most "
    "important action. If the plan does not cover something, say so and give the most "
    "sensible survival guidance anyway. Stay in character."
)


def _chunk(text, size=900, overlap=150):
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start:start + size])
        start += size - overlap
    return [c.strip() for c in chunks if c.strip()]


def get_collection():
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    return client.get_or_create_collection(COLLECTION)


def ensure_index():
    col = get_collection()
    if col.count() > 0:
        return col
    reader = PdfReader(str(PDF_PATH))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    chunks = _chunk(text)
    col.add(ids=[f"chunk-{i}" for i in range(len(chunks))], documents=chunks)
    return col


def retrieve(question, k=5):
    col = ensure_index()
    res = col.query(query_texts=[question], n_results=k)
    return res["documents"][0] if res["documents"] else []


def answer(question, recent_events, location=None, k=5):
    """Yields tokens of Claude's streamed survival advice.

    If ``location`` is provided (the joined survivor's location), the advice is
    tailored to that location.
    """
    client = anthropic.Anthropic()
    context = "\n\n---\n\n".join(retrieve(question, k))
    feed = "\n".join(
        f"- [{e['severity'].upper()}] {e['city']}, {e['state']}: {e['headline']}"
        for e in recent_events[:25]
    ) or "No active reports."

    location_line = (
        f"SURVIVOR LOCATION: {location}. Tailor your advice to this location and "
        f"reference nearby reports from the feed when relevant.\n\n"
        if location else ""
    )
    user = (
        f"ZOMBIE PLAN EXCERPTS:\n{context}\n\n"
        f"LIVE EVENT FEED (most recent):\n{feed}\n\n"
        f"{location_line}"
        f"SURVIVOR QUESTION:\n{question}"
    )
    with client.messages.stream(
        model=MODEL,
        max_tokens=1500,
        system=[{"type": "text", "text": RAG_SYSTEM,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
        output_config={"effort": "medium"},
    ) as stream:
        for token in stream.text_stream:
            yield token
