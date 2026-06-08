import json
import threading
import time
from datetime import datetime, timezone

import anthropic

import db

MODEL = "claude-opus-4-8"
BATCH_SIZE = 50
INTERVAL_SECONDS = 60      # min seconds between generated batches
ACTIVE_TIMEOUT = 30        # consider a viewer "present" if seen within this window
TICK_SECONDS = 5           # how often the thread re-checks whether to generate

SYSTEM_PROMPT = (
    "You are the automated feed for the National Zombie Outbreak Monitoring System, "
    "a fictional emergency broadcast service. You invent short, eerie, varied news "
    "flashes about a zombie outbreak unfolding across the United States. Events are "
    "fictional and atmospheric but grounded in real US cities and states. Vary tone, "
    "location, and severity widely. Never break character."
)

EVENT_SCHEMA = {
    "type": "object",
    "properties": {
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "state": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["low", "moderate", "high", "critical"],
                    },
                    "headline": {"type": "string"},
                    "detail": {"type": "string"},
                },
                "required": ["city", "state", "severity", "headline", "detail"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["events"],
    "additionalProperties": False,
}


def generate_batch(client, wave):
    prompt = (
        f"Generate exactly {BATCH_SIZE} NEW, distinct zombie-outbreak field reports for "
        f"emergency wave #{wave}. Spread them across many different US states and cities. "
        f"Keep each headline under 90 characters; each detail is one or two eerie "
        f"sentences. Make this wave feel different from earlier waves."
    )
    resp = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=[{"type": "text", "text": SYSTEM_PROMPT,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt}],
        output_config={
            "effort": "low",
            "format": {"type": "json_schema", "schema": EVENT_SCHEMA},
        },
    )
    text = next(b.text for b in resp.content if b.type == "text")
    return json.loads(text)["events"][:BATCH_SIZE]


class EventGenerator:
    """Background daemon that generates 50 events/min ONLY while a viewer is active.

    The UI calls heartbeat() on every panel refresh. If no heartbeat has arrived
    within ACTIVE_TIMEOUT seconds, the thread idles and makes no API calls.
    """

    def __init__(self):
        self._client = anthropic.Anthropic()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._lock = threading.Lock()
        self._started = False
        self._last_seen = 0.0     # monotonic time of last viewer heartbeat
        self._last_gen = 0.0      # monotonic time of last generated batch
        self.last_error = None
        self.waves = 0

    def start(self):
        if not self._started:
            self._started = True
            db.init_db()
            self._thread.start()

    def heartbeat(self):
        with self._lock:
            self._last_seen = time.monotonic()

    def is_active(self):
        with self._lock:
            return (time.monotonic() - self._last_seen) < ACTIVE_TIMEOUT

    def _run(self):
        while True:
            if self.is_active():
                due = (time.monotonic() - self._last_gen) >= INTERVAL_SECONDS
                if self._last_gen == 0.0 or due:
                    try:
                        self.waves += 1
                        events = generate_batch(self._client, self.waves)
                        db.insert_events(
                            events, datetime.now(timezone.utc).isoformat()
                        )
                        self.last_error = None
                    except Exception as exc:  # keep idling on transient API errors
                        self.last_error = str(exc)
                    self._last_gen = time.monotonic()
            time.sleep(TICK_SECONDS)
