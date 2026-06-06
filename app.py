import os

import streamlit as st
from dotenv import load_dotenv

import db
import rag
from events import EventGenerator

load_dotenv()

st.set_page_config(page_title="Zombie Outbreak Monitor", page_icon="🧟",
                   layout="wide")

EERIE_CSS = """
<style>
.stApp { background: radial-gradient(circle at 50% 0%, #160000 0%, #050505 70%);
         color: #c9d1c9; font-family: 'Courier New', monospace; }
h1.glitch { color:#9bff9b; letter-spacing:3px; text-shadow:0 0 8px #1bff1b,0 0 18px #066;
            animation: flick 3s infinite; }
@keyframes flick { 0%,19%,21%,100%{opacity:1} 20%{opacity:.4} 50%{opacity:.85} }
.event { background:rgba(20,0,0,.55); padding:8px 10px; margin:6px 0; border-radius:4px;
         font-size:.86rem; line-height:1.25; }
.event .sev { color:#ff5b5b; font-size:.74rem; }
.event .hl  { color:#f0f0f0; }
.event .dt  { color:#8aa08a; font-style:italic; font-size:.8rem; }
.q { color:#9bff9b; margin-top:12px; font-weight:bold; }
.a { background:rgba(0,15,0,.4); border-left:3px solid #1bff1b; padding:10px;
     margin:6px 0 14px; border-radius:4px; }
[data-testid="stForm"] { border:1px solid #2a0000; background:rgba(15,0,0,.4); }
</style>
"""
st.markdown(EERIE_CSS, unsafe_allow_html=True)

SEV_COLORS = {"low": "#7CFC00", "moderate": "#FFD300",
              "high": "#FF8C00", "critical": "#FF2D2D"}


@st.cache_resource
def boot():
    db.init_db()
    rag.ensure_index()            # build the vector index once (first launch)
    gen = EventGenerator()
    gen.start()                   # background feed: 50 events / minute (while watched)
    return gen


@st.fragment(run_every="3s")
def updates_panel():
    boot().heartbeat()            # signal "a viewer is watching" -> feed stays live
    active = boot().is_active()
    status = "🟢 FEED LIVE" if active else "⚪ FEED IDLE"
    events = db.recent_events(limit=60)
    st.markdown(f"#### ☣ {status} · {db.count_events()}/1000 logged")
    if not events:
        st.caption("Awaiting first transmission…")
    for e in events:
        color = SEV_COLORS.get(e["severity"], "#bbbbbb")
        st.markdown(
            f"<div class='event' style='border-left:4px solid {color}'>"
            f"<span style='color:{color}'>●</span> "
            f"<b>{e['city']}, {e['state']}</b> "
            f"<span class='sev'>[{e['severity'].upper()}]</span><br>"
            f"<span class='hl'>{e['headline']}</span><br>"
            f"<span class='dt'>{e['detail']}</span></div>",
            unsafe_allow_html=True,
        )


def main():
    if not os.getenv("ANTHROPIC_API_KEY"):
        st.error("ANTHROPIC_API_KEY is not set. Add it to a .env file and restart.")
        st.stop()

    gen = boot()
    st.markdown("<h1 class='glitch'>🧟 ZOMBIE OUTBREAK MONITOR</h1>",
                unsafe_allow_html=True)
    if gen.last_error:
        st.warning(f"Feed degraded: {gen.last_error}")

    left, mid = st.columns([1, 1.6], gap="large")

    with left:
        updates_panel()

    with mid:
        st.markdown("#### 🛰 SURVIVAL CONSOLE")
        st.caption("Ask what to do next, given the official Zombie Plan and the live feed.")

        if "history" not in st.session_state:
            st.session_state.history = []
        for q, a in st.session_state.history:
            st.markdown(f"<div class='q'>▸ {q}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='a'>{a}</div>", unsafe_allow_html=True)

        with st.form("ask", clear_on_submit=True):
            question = st.text_input(
                "What should we do next?",
                placeholder="e.g. The horde is two blocks away — what now?",
            )
            submitted = st.form_submit_button("TRANSMIT")

        if submitted and question:
            st.markdown(f"<div class='q'>▸ {question}</div>", unsafe_allow_html=True)
            recent = db.recent_events(limit=25)
            answer_text = st.write_stream(rag.answer(question, recent))
            st.session_state.history.append((question, answer_text))


if __name__ == "__main__":
    main()
