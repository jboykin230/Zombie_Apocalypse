import os
from datetime import datetime, timezone

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

import db
import geo
import rag
import ui_components as ui
from events import EventGenerator

PROXIMITY_MILES = 500  # warn the survivor about outbreaks within this radius

load_dotenv()

st.set_page_config(page_title="Zombie Outbreak Monitor", page_icon="🧟",
                   layout="wide")

EERIE_CSS = """
<style>
.stApp { background: radial-gradient(circle at 50% 0%, #160000 0%, #050505 70%);
         color: #c9d1c9; font-family: 'Courier New', monospace; }
h1.glitch { color:#9bff9b; letter-spacing:3px; margin-bottom:2px;
            text-shadow:0 0 8px #1bff1b,0 0 18px #066; animation: flick 3s infinite; }
h2.glitch.sub { color:#9bff9b; letter-spacing:2px; margin-top:0; font-size:1.15rem;
            text-shadow:0 0 8px #1bff1b,0 0 18px #066; animation: flick 3s infinite; }
.subnote { text-align:center; font-size:0.8rem; color:#7fae7f; letter-spacing:1px;
           margin-top:2px; }
.subnote a { color:#9bff9b; text-decoration:underline; }
.subnote a:hover { color:#1bff1b; text-shadow:0 0 8px #1bff1b; }
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
    db.init_db()
    db.clear_queries()            # console history starts over on each program restart
    rag.ensure_index()            # build the vector index once (first launch)
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


@st.dialog("⚠ PROXIMITY ALERT")
def proximity_dialog(alerts, loc):
    st.markdown(
        f"<div style='color:#ff5b5b;font-weight:bold;letter-spacing:1px'>"
        f"{len(alerts)} outbreak{'s' if len(alerts) != 1 else ''} within "
        f"{PROXIMITY_MILES} miles of {loc}:</div>",
        unsafe_allow_html=True,
    )
    for e, dist in alerts:
        c = ui.SEV_COLORS.get(e["severity"], "#bbb")
        st.markdown(
            f"<div style='background:rgba(20,0,0,.55);border-left:4px solid {c};"
            f"padding:8px 10px;margin:8px 0;border-radius:4px'>"
            f"<b>{e['city']}, {e['state']}</b> "
            f"<span style='color:{c}'>[{e['severity'].upper()}]</span> "
            f"<span style='color:#8aa08a'>· ~{round(dist)} mi away</span><br>"
            f"<span style='color:#f0f0f0'>{e['headline']}</span><br>"
            f"<span style='color:#9bbf9b;font-style:italic'>{e['detail']}</span></div>",
            unsafe_allow_html=True,
        )


def _check_proximity(events):
    """Pop a warning for not-yet-seen events within PROXIMITY_MILES of the survivor.

    Only runs once a survivor has enlisted (name + location). Each event is
    alerted at most once (tracked in ss.alerted) so the popup doesn't re-fire.
    """
    ss = st.session_state
    if not ss.user_marker:
        return
    loc = ss.user_marker["label"]
    alerts = []
    for e in events:
        if e["id"] in ss.alerted:
            continue
        dist = geo.miles_between(loc, f"{e['city']}, {e['state']}")
        if dist is not None and dist <= PROXIMITY_MILES:
            ss.alerted.add(e["id"])
            alerts.append((e, dist))
    if alerts:
        alerts.sort(key=lambda x: x[1])      # nearest first
        proximity_dialog(alerts, loc)


@st.fragment(run_every="10s")
def ticker_fragment():
    ui.render_ticker(db.recent_events(40))   # scrolling banner of incoming events


@st.fragment(run_every="10s")
def feed_fragment():
    boot().heartbeat()                       # "a viewer is watching" -> feed stays live
    events = db.recent_events(50)
    batch_id, _ = db.latest_batch()
    ui.render_feed(events, batch_id, height=540)
    _check_proximity(events)                  # warn on nearby outbreaks (if enlisted)


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

    # Previous Q&A collapse to an expandable single line; only the answer to the
    # newest query (streamed below) stays open until the next query is issued.
    for q, a, qloc in st.session_state.history:
        tag = f" · {qloc}" if qloc else ""
        with st.expander(f"▸ {q}{tag}", expanded=False):
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
        answer_text = st.write_stream(
            rag.answer(question, recent, location=loc,
                       history=st.session_state.history)
        )
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
    ss.setdefault("alerted", set())          # event ids already proximity-warned

    gen = boot()

    ticker_fragment()        # scrolling banner of incoming events across the top

    left_col, right_col = st.columns([1.3, 1], gap="medium")

    with left_col:
        st.markdown("<h1 class='glitch'>🧟 ZOMBIE OUTBREAK MONITOR</h1>",
                    unsafe_allow_html=True)
        st.markdown("<h2 class='glitch sub'>(Okeechobee, FL Survival Portal)</h2>",
                    unsafe_allow_html=True)
        st.markdown(
            "<div class='subnote'>"
            "<a href='https://cdn7.creativecirclemedia.com/scfl/files/"
            "20250616-093803-1af-Annex%20Z.pdf' target='_blank' rel='noopener'>"
            "Actual Official Document</a></div>",
            unsafe_allow_html=True,
        )
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
