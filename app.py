import os
from datetime import datetime, timezone

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

import db
import rag
import ui_components as ui
from events import EventGenerator

load_dotenv()

st.set_page_config(page_title="Zombie Outbreak Monitor", page_icon="🧟",
                   layout="wide")

EERIE_CSS = """
<style>
.stApp { background: radial-gradient(circle at 50% 0%, #160000 0%, #050505 70%);
         color: #c9d1c9; font-family: 'Courier New', monospace; }
h1.glitch { color:#9bff9b; letter-spacing:3px; margin-bottom:2px;
            text-shadow:0 0 8px #1bff1b,0 0 18px #066; animation: flick 3s infinite; }
@keyframes flick { 0%,19%,21%,100%{opacity:1} 20%{opacity:.4} 50%{opacity:.85} }
.st-key-join_btn button { background:transparent; border:none; color:#ff5b5b;
    font-family:'Courier New',monospace; font-weight:bold; letter-spacing:2px;
    text-decoration:underline; padding:0; font-size:1rem; box-shadow:none; }
.st-key-join_btn button:hover { color:#ff2d2d; text-shadow:0 0 8px #ff2d2d; }
.joined { color:#9bff9b; font-weight:bold; letter-spacing:1px; }
.q { color:#9bff9b; margin-top:12px; font-weight:bold; }
.a { background:rgba(0,15,0,.4); border-left:3px solid #1bff1b; padding:10px;
     margin:6px 0 14px; border-radius:4px; }
[data-testid="stForm"] { border:1px solid #2a0000; background:rgba(15,0,0,.4); }
</style>
"""
st.markdown(EERIE_CSS, unsafe_allow_html=True)


def _now():
    return datetime.now(timezone.utc).isoformat()


@st.cache_resource
def boot():
    db.reset_db()                 # fresh SQLite store on every app startup
    rag.reset_index()             # drop & rebuild the vector index on every startup
    gen = EventGenerator()
    gen.start()                   # background feed: 50 events / minute (while watched)
    return gen


def _update_persistent(batch_id, batch):
    """When a new batch arrives, fold the previous batch's high/critical events
    into the persistent set (low/moderate are dropped) and make the new batch
    the current one. Only high/critical markers survive across minutes.
    """
    ss = st.session_state
    if batch_id and batch_id != ss.current_batch_id:
        for e in ss.current_batch:
            if e["severity"] in ("high", "critical"):
                ss.persistent.append(
                    {k: e[k] for k in ("city", "state", "severity", "headline", "detail")}
                )
        ss.current_batch = batch
        ss.current_batch_id = batch_id


@st.dialog("☣ JOIN THE SURVIVORS")
def join_dialog():
    components.html(ui.tutorial_html(), height=220, scrolling=False)
    st.caption("Now enlist:")
    with st.form("join_form"):
        name = st.text_input("NAME")
        location = st.text_input("LOCATION", placeholder="e.g. Austin, Texas")
        if st.form_submit_button("ENLIST"):
            if name.strip() and location.strip():
                db.add_user(name.strip(), location.strip(), _now())
                st.session_state.user_marker = {
                    "label": location.strip(), "name": name.strip()
                }
                st.rerun()
            else:
                st.error("Both NAME and LOCATION are required.")


@st.fragment(run_every="10s")
def feed_fragment():
    boot().heartbeat()                       # "a viewer is watching" -> feed stays live
    batch_id, _ = db.latest_batch()
    ui.render_feed(db.recent_events(50), batch_id, height=540)


@st.fragment(run_every="10s")
def map_fragment():
    batch_id, batch = db.latest_batch()
    _update_persistent(batch_id, batch)
    ui.render_map(
        batch=st.session_state.current_batch,
        batch_id=st.session_state.current_batch_id,
        persistent=st.session_state.persistent,
        user_marker=st.session_state.user_marker,
        height=220,
    )


def console_block():
    st.markdown("#### 🛰 SURVIVAL CONSOLE")
    loc = st.session_state.user_marker["label"] if st.session_state.user_marker else None
    st.caption(
        f"Advising for **{loc}**." if loc
        else "Ask what to do next, given the Zombie Plan and the live feed."
    )

    for q, a, qloc in st.session_state.history:
        tag = f" · {qloc}" if qloc else ""
        st.markdown(f"<div class='q'>▸ {q}{tag}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='a'>{a}</div>", unsafe_allow_html=True)

    with st.form("ask", clear_on_submit=True):
        question = st.text_input(
            "What should we do next?",
            placeholder="e.g. The horde is two blocks away — what now?",
        )
        submitted = st.form_submit_button("TRANSMIT")

    if submitted and question:
        st.markdown(f"<div class='q'>▸ {question}</div>", unsafe_allow_html=True)
        recent = db.recent_events(25)
        answer_text = st.write_stream(rag.answer(question, recent, location=loc))
        db.log_query(loc, question, answer_text, _now())
        st.session_state.history.append((question, answer_text, loc))


def main():
    if not os.getenv("ANTHROPIC_API_KEY"):
        st.error("ANTHROPIC_API_KEY is not set. Add it to a .env file and restart.")
        st.stop()

    ss = st.session_state
    ss.setdefault("persistent", [])
    ss.setdefault("current_batch", [])
    ss.setdefault("current_batch_id", "")
    ss.setdefault("user_marker", None)
    ss.setdefault("history", [])

    gen = boot()

    left_col, right_col = st.columns([1.3, 1], gap="medium")

    with left_col:
        st.markdown("<h1 class='glitch'>🧟 ZOMBIE OUTBREAK MONITOR</h1>",
                    unsafe_allow_html=True)
        if ss.user_marker:
            st.markdown(
                f"<div class='joined'>✔ ENLISTED: {ss.user_marker['name']} — "
                f"{ss.user_marker['label']}</div>",
                unsafe_allow_html=True,
            )
        else:
            if st.button("JOIN THE SURVIVORS!", key="join_btn"):
                join_dialog()

        if gen.last_error:
            st.warning(f"Feed degraded: {gen.last_error}")

        st.markdown("##### ☣ LIVE FEED")
        feed_fragment()

    with right_col:
        map_fragment()
        console_block()


if __name__ == "__main__":
    main()
