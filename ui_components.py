"""Custom HTML/JS UI components: the live feed, the interactive US map, and
the JOIN tutorial. Each is rendered via st.components.v1.html (a sandboxed
iframe). Data flows Python -> iframe only; all data *entry* is done with native
Streamlit widgets in app.py so it reliably reaches SQLite.
"""
import json

import streamlit as st
import streamlit.components.v1 as components

PAGE_BG = "radial-gradient(circle at 50% 0%, #160000 0%, #050505 70%)"

SEV_COLORS = {
    "low": "#7CFC00",
    "moderate": "#FFD300",
    "high": "#FF8C00",
    "critical": "#FF2D2D",
}
# Initial bomb-burst radius (px) — bigger = more severe.
SEV_BOMB = {"low": 16, "moderate": 24, "high": 34, "critical": 46}
# Persistent dot radius (px).
SEV_DOT = {"low": 4, "moderate": 5, "high": 6, "critical": 7}

US_ATLAS = "https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json"
D3 = "https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"
TOPOJSON = "https://cdn.jsdelivr.net/npm/topojson-client@3/dist/topojson-client.min.js"


# ===================================================================== feed

def render_feed(events, batch_id, height=520):
    """Latest-50 feed. Entries fade in only when a new batch arrives
    (guarded by sessionStorage on batch_id), not on every refresh.
    """
    html = (
        _FEED_HTML
        .replace("__BG__", PAGE_BG)
        .replace("__HEIGHT__", str(height))
        .replace("__BATCH_ID__", json.dumps(batch_id or ""))
        .replace("__EVENTS__", json.dumps(events))
        .replace("__COLORS__", json.dumps(SEV_COLORS))
    )
    components.html(html, height=height, scrolling=False)


_FEED_HTML = """
<!doctype html><html><head><meta charset="utf-8"><style>
  html,body{margin:0;padding:0;background:__BG__;
    font-family:'Courier New',monospace;color:#c9d1c9;}
  #wrap{height:__HEIGHT__px;overflow-y:auto;padding:2px 4px;}
  #wrap::-webkit-scrollbar{width:6px}
  #wrap::-webkit-scrollbar-thumb{background:#3a0000;border-radius:3px}
  .event{background:rgba(20,0,0,.55);padding:8px 10px;margin:6px 0;border-radius:4px;
    font-size:.86rem;line-height:1.25;opacity:1;}
  .event.fresh{animation:fin .6s ease both;}
  @keyframes fin{from{opacity:0;transform:translateY(-8px)}to{opacity:1;transform:none}}
  .sev{font-size:.72rem}
  .hl{color:#f0f0f0}
  .dt{color:#8aa08a;font-style:italic;font-size:.8rem}
  .empty{color:#7a7a7a;padding:14px}
</style></head><body>
<div id="wrap"></div>
<script>
  const EVENTS = __EVENTS__;
  const COLORS = __COLORS__;
  const BATCH  = __BATCH_ID__;
  const wrap = document.getElementById('wrap');
  const last = sessionStorage.getItem('feedBatch');
  const isNew = BATCH && BATCH !== last;
  if (isNew) sessionStorage.setItem('feedBatch', BATCH);

  if (!EVENTS.length) {
    wrap.innerHTML = "<div class='empty'>Awaiting first transmission&hellip;</div>";
  } else {
    EVENTS.forEach((e, i) => {
      const c = COLORS[e.severity] || '#bbb';
      const d = document.createElement('div');
      d.className = 'event' + (isNew ? ' fresh' : '');
      d.style.borderLeft = '4px solid ' + c;
      if (isNew) d.style.animationDelay = (i * 0.02) + 's';
      d.innerHTML =
        "<span style='color:"+c+"'>&#9679;</span> <b>"+e.city+", "+e.state+"</b> "+
        "<span class='sev' style='color:"+c+"'>["+e.severity.toUpperCase()+"]</span><br>"+
        "<span class='hl'>"+e.headline+"</span><br>"+
        "<span class='dt'>"+e.detail+"</span>";
      wrap.appendChild(d);
    });
  }
</script></body></html>
"""


# =================================================================== ticker

def render_ticker(events, height=52):
    """A right-to-left scrolling news ticker of incoming events.

    Each entry is two lines — ``City, State`` on top, the headline below — and
    entries are separated by a full-height vertical line. Scrolls at a constant
    speed regardless of how many events are present.
    """
    items = [
        {"loc": f"{e['city']}, {e['state']}", "title": e["headline"]}
        for e in events
    ]
    html = (
        _TICKER_HTML
        .replace("__BG__", PAGE_BG)
        .replace("__HEIGHT__", str(height))
        .replace("__ITEMS__", json.dumps(items))
    )
    components.html(html, height=height, scrolling=False)


_TICKER_HTML = """
<!doctype html><html><head><meta charset="utf-8"><style>
  html,body{margin:0;padding:0;background:__BG__;overflow:hidden;
    font-family:'Courier New',monospace;}
  .ticker{height:__HEIGHT__px;display:flex;align-items:stretch;overflow:hidden;
    white-space:nowrap;border-top:1px solid #2a0000;border-bottom:1px solid #2a0000;
    background:rgba(15,0,0,.55);}
  .track{display:inline-flex;align-items:stretch;will-change:transform;
    animation:scroll linear infinite;}
  .item{display:inline-flex;flex-direction:column;justify-content:center;
    line-height:1.3;}
  .loc{color:#9bff9b;font-weight:bold;font-size:.82rem;
    text-shadow:0 0 6px rgba(27,255,27,.4);}
  .ttl{color:#d6e6d6;font-size:.78rem;}
  .sep{width:1px;background:#7a2d2d;align-self:stretch;margin:8px 16px;flex:0 0 auto;}
  .empty{color:#7a7a7a;padding-left:14px;align-self:center;font-size:.82rem;}
  @keyframes scroll{from{transform:translateX(0)}to{transform:translateX(-50%)}}
</style></head><body>
<div class="ticker"><div class="track" id="track"></div></div>
<script>
  const ITEMS = __ITEMS__;
  const track = document.getElementById('track');

  function sep(){ const s=document.createElement('span'); s.className='sep'; return s; }
  function item(e){
    const wrap=document.createElement('span'); wrap.className='item';
    const loc=document.createElement('span'); loc.className='loc'; loc.textContent=e.loc;
    const ttl=document.createElement('span'); ttl.className='ttl'; ttl.textContent=e.title;
    wrap.appendChild(loc); wrap.appendChild(ttl); return wrap;   // location on top
  }

  if (!ITEMS.length){
    track.parentNode.innerHTML="<div class='empty'>Awaiting transmissions&hellip;</div>";
  } else {
    // build the row, then duplicate it so translateX(-50%) loops seamlessly
    function fill(){ ITEMS.forEach(e=>{ track.appendChild(item(e)); track.appendChild(sep()); }); }
    fill(); fill();
    const SPEED = 80;                                   // pixels per second
    const copyWidth = track.scrollWidth / 2;
    track.style.animationDuration = (copyWidth / SPEED) + 's';
  }
</script></body></html>
"""


# ====================================================================== map

def render_map(batch, batch_id, persistent, user_marker, height=240):
    """Interactive US map.

    batch          : latest 50 events (all severities) shown this minute
    batch_id       : the batch timestamp; explosions animate only when it changes
    persistent     : high/critical markers from earlier minutes (drawn static)
    user_marker    : {"label","name"} of the joined survivor, or None
    """
    html = (
        _MAP_HTML
        .replace("__BG__", PAGE_BG)
        .replace("__HEIGHT__", str(height))
        .replace("__US_ATLAS__", US_ATLAS)
        .replace("__D3__", D3)
        .replace("__TOPOJSON__", TOPOJSON)
        .replace("__BATCH_ID__", json.dumps(batch_id or ""))
        .replace("__BATCH__", json.dumps(batch))
        .replace("__PERSIST__", json.dumps(persistent))
        .replace("__USER__", json.dumps(user_marker))
        .replace("__COLORS__", json.dumps(SEV_COLORS))
        .replace("__BOMB__", json.dumps(SEV_BOMB))
        .replace("__DOT__", json.dumps(SEV_DOT))
    )
    components.html(html, height=height + 4, scrolling=False)


_MAP_HTML = """
<!doctype html><html><head><meta charset="utf-8">
<script src="__D3__"></script>
<script src="__TOPOJSON__"></script>
<style>
  html,body{margin:0;padding:0;background:__BG__;overflow:hidden;
    font-family:'Courier New',monospace;}
  #map{position:relative;width:100%;height:__HEIGHT__px;}
  svg{width:100%;height:100%;display:block;background:transparent;}
  .outline{fill:none;stroke:#2f6b2f;stroke-width:1.1;
    filter:drop-shadow(0 0 3px rgba(40,255,40,.25));}
  .borders{fill:none;stroke:rgba(120,255,120,.10);stroke-width:.5;}
  .dot{cursor:pointer;}
  .popup{position:absolute;z-index:20;width:72%;max-width:300px;
    max-height:calc(100% - 16px);overflow-y:auto;background:rgba(10,0,0,.96);
    border:1px solid #5a0000;border-radius:6px;padding:10px 12px;color:#e8e8e8;
    font-size:.8rem;line-height:1.35;box-shadow:0 0 18px rgba(0,0,0,.8);
    pointer-events:auto;}
  .popup b{color:#ff8c8c}
  .popup .pd{color:#9bbf9b;font-style:italic;margin-top:4px;display:block}
  .err{color:#ff6b6b;padding:14px;font-size:.8rem}
  .person{font-size:54px;pointer-events:none;filter:drop-shadow(0 0 7px #1bff1b)}
</style></head><body>
<div id="map"></div>
<script>
const BATCH   = __BATCH__;
const BATCH_ID= __BATCH_ID__;
const PERSIST = __PERSIST__;
const USER    = __USER__;
const COLORS  = __COLORS__;
const BOMB    = __BOMB__;
const DOT     = __DOT__;

const root = document.getElementById('map');
const W = root.clientWidth || 360;
const H = __HEIGHT__;

// deterministic [0,1) hash so a given event always jitters to the same spot
function rng(str){let h=1779033703^str.length;for(let i=0;i<str.length;i++){
  h=Math.imul(h^str.charCodeAt(i),3432918353);h=h<<13|h>>>19;}
  return function(){h=Math.imul(h^h>>>16,2246822507);h=Math.imul(h^h>>>13,3266489909);
  return((h^=h>>>16)>>>0)/4294967296;};}

function draw(us){
  const sf = topojson.feature(us, us.objects.states);
  const proj = d3.geoAlbersUsa().fitSize([W, H], sf);
  const path = d3.geoPath(proj);
  const cen = {};
  sf.features.forEach(f => { cen[f.properties.name] = path.centroid(f); });

  const svg = d3.select(root).append('svg').attr('viewBox','0 0 '+W+' '+H);
  svg.append('path').attr('class','borders')
     .attr('d', path(topojson.mesh(us, us.objects.states, (a,b)=>a!==b)));
  svg.append('path').attr('class','outline')
     .attr('d', path(topojson.mesh(us, us.objects.states, (a,b)=>a===b)));

  let popup = null;
  function closePopup(){ if(popup){popup.remove();popup=null;} }
  document.addEventListener('click', closePopup);

  function pos(ev, idx){
    const c = cen[ev.state];
    if(!c) return null;
    const r = rng(ev.state + ev.city + ev.headline + idx);
    const ang = r() * 6.2832, rad = r() * 16;
    return [c[0] + Math.cos(ang)*rad, c[1] + Math.sin(ang)*rad];
  }

  function openPopup(inner){
    closePopup();
    popup = document.createElement('div');
    popup.className = 'popup';
    popup.innerHTML = inner;
    root.appendChild(popup);
    // center the bubble in the map so the full contents are always visible
    popup.style.left = '50%';
    popup.style.top = '50%';
    popup.style.transform = 'translate(-50%, -50%)';
    popup.addEventListener('click', e => e.stopPropagation());
  }

  function showPopup(ev){
    const c = COLORS[ev.severity] || '#bbb';
    openPopup(
      "<b>"+ev.city+", "+ev.state+"</b> "+
      "<span style='color:"+c+"'>["+ev.severity.toUpperCase()+"]</span><br>"+
      ev.headline + "<span class='pd'>"+ev.detail+"</span>");
  }

  function dot(ev, idx){
    const p = pos(ev, idx); if(!p) return;
    const c = COLORS[ev.severity] || '#bbb';
    svg.append('circle').attr('class','dot')
      .attr('cx',p[0]).attr('cy',p[1]).attr('r', DOT[ev.severity]||4)
      .attr('fill',c).attr('stroke','#000').attr('stroke-width',.5)
      .style('filter','drop-shadow(0 0 3px '+c+')')
      .on('click', (e)=>{ e.stopPropagation(); showPopup(ev); });
  }

  function bomb(ev, idx){
    const p = pos(ev, idx); if(!p) return;
    const c = COLORS[ev.severity] || '#bbb';
    const R = BOMB[ev.severity] || 16;
    const g = svg.append('g');
    [0,1,2].forEach(k=>{
      g.append('circle').attr('cx',p[0]).attr('cy',p[1]).attr('r',2)
       .attr('fill','none').attr('stroke',c).attr('stroke-width',2.5).attr('opacity',.9)
       .transition().delay(k*70).duration(620).ease(d3.easeCubicOut)
       .attr('r', R*(1-k*0.18)).attr('stroke-width',.4).attr('opacity',0).remove();
    });
    const core = g.append('circle').attr('cx',p[0]).attr('cy',p[1]).attr('r',R*0.5)
       .attr('fill',c).attr('opacity',.85);
    core.transition().duration(420).ease(d3.easeCubicOut)
       .attr('r',R*0.12).attr('opacity',0)
       .on('end',()=>{ g.remove(); dot(ev, idx); });
  }

  // persistent (high/critical from earlier minutes) — always static
  PERSIST.forEach((e,i)=> dot(e, 'p'+i));

  // current batch: animate explosions once per new batch, else draw static
  const lastAnim = sessionStorage.getItem('mapBatch');
  if (BATCH_ID && BATCH_ID !== lastAnim){
    sessionStorage.setItem('mapBatch', BATCH_ID);
    BATCH.forEach((e,i)=> setTimeout(()=>bomb(e,i), i*1000));  // 1 per second
  } else {
    BATCH.forEach((e,i)=> dot(e,i));
  }

  // persistent person marker for the joined survivor
  if (USER){
    let st = null;
    for (const name in cen){
      if (USER.label && USER.label.toLowerCase().includes(name.toLowerCase())){ st = name; break; }
    }
    const c = st ? cen[st] : [W/2, H/2];
    // Drawn last so it sits on top visually, but pointer-events:none (see CSS)
    // lets clicks pass through to the event circles around and beneath it.
    svg.append('text').attr('class','person').attr('x',c[0]).attr('y',c[1])
       .attr('text-anchor','middle').attr('dy','.35em').text('\\uD83E\\uDDCD');
  }
}

d3.json("__US_ATLAS__").then(draw).catch(err=>{
  root.innerHTML = "<div class='err'>Map failed to load (need internet for the "+
    "US map data): "+err+"</div>";
});
</script></body></html>
"""


# =================================================================== tutorial

def tutorial_html(height=210):
    """Cosmetic auto-playing 'how to join' demo shown above the real form."""
    return _TUTORIAL_HTML.replace("__BG__", PAGE_BG).replace("__HEIGHT__", str(height))


_TUTORIAL_HTML = """
<!doctype html><html><head><meta charset="utf-8"><style>
  html,body{margin:0;padding:0;background:__BG__;font-family:'Courier New',monospace;
    color:#c9d1c9;overflow:hidden;}
  #stage{position:relative;height:__HEIGHT__px;padding:10px 14px;box-sizing:border-box;}
  .fld{border:1px solid #3a0000;border-radius:5px;padding:8px 10px;margin:8px 0;
    background:rgba(15,0,0,.5);transition:all .4s;}
  .fld .lab{font-size:.7rem;color:#9bbf9b;letter-spacing:1px;}
  .fld .box{height:16px;margin-top:4px;border-bottom:1px dashed #555;}
  .glow{border-color:#1bff1b;box-shadow:0 0 12px rgba(27,255,27,.5);}
  .tip{position:absolute;right:14px;background:#0a1a0a;border:1px solid #1bff1b;
    border-radius:6px;padding:6px 10px;font-size:.74rem;color:#bfffbf;opacity:0;
    transition:opacity .4s;max-width:200px;}
  #mini{position:absolute;right:14px;bottom:10px;width:120px;height:74px;
    border:1px solid #2f6b2f;border-radius:6px;opacity:.55;}
  .bub{position:absolute;width:14px;height:14px;border-radius:50%;background:#FF2D2D;
    box-shadow:0 0 10px #FF2D2D;opacity:0;}
</style></head><body>
<div id="stage">
  <div class="fld" id="fname"><div class="lab">NAME</div><div class="box"></div></div>
  <div class="fld" id="floc"><div class="lab">LOCATION</div><div class="box"></div></div>
  <div class="tip" id="tip"></div>
  <div id="mini"><div class="bub" id="bub"></div></div>
</div>
<script>
  const tip=document.getElementById('tip');
  const fn=document.getElementById('fname'), fl=document.getElementById('floc');
  const bub=document.getElementById('bub');
  function showTip(t,top){tip.textContent=t;tip.style.top=top+'px';tip.style.opacity=1;}
  function run(){
    fn.classList.add('glow'); showTip('Enter your name so we can track you!',14);
    setTimeout(()=>{ fn.classList.remove('glow'); tip.style.opacity=0; },3000);
    setTimeout(()=>{ fl.classList.add('glow'); showTip('Tell us where you are!!!',60); },3300);
    setTimeout(()=>{ fl.classList.remove('glow'); tip.style.opacity=0; },6300);
    setTimeout(()=>{ bub.style.left='52px'; bub.style.top='30px';
      bub.style.opacity=1; bub.style.transition='opacity .4s';
      showTip('\\u2026and mark it on the map',120); },6600);
    setTimeout(()=>{ bub.style.opacity=0; tip.style.opacity=0;
      document.getElementById('stage').style.transition='opacity .6s';
      document.getElementById('stage').style.opacity=.25; },9600);
  }
  run();
</script></body></html>
"""
