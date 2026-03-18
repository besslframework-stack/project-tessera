"""Web dashboard for Tessera — full SPA served from FastAPI.

Single-page application with hash-based routing, Chart.js, Mermaid,
dark theme, and full CRUD management capabilities.
"""

from __future__ import annotations

import html
import json
import logging

logger = logging.getLogger(__name__)


def _card(title: str, value: str, subtitle: str = "", color: str = "blue") -> str:
    """Render a stat card HTML snippet using CSS classes."""
    esc_title = html.escape(title)
    esc_value = html.escape(str(value))
    esc_sub = html.escape(subtitle) if subtitle else ""
    sub_html = (
        f'<div class="card-subtitle">{esc_sub}</div>' if esc_sub else ""
    )
    return f"""
        <div class="card card--{html.escape(color)}">
          <div class="card-label">{esc_title}</div>
          <div class="card-value">{esc_value}</div>
          {sub_html}
        </div>"""


def render_dashboard(stats: dict) -> str:
    """Render the full SPA dashboard HTML page.

    Args:
        stats: Dict with keys: memory_count, entity_count, relationship_count,
               health_score, contradiction_count, cluster_count,
               recent_memories, entity_graph_mermaid, version.

    Returns:
        Complete HTML string for the single-page application.
    """
    memory_count = stats.get("memory_count", 0)
    entity_count = stats.get("entity_count", 0)
    rel_count = stats.get("relationship_count", 0)
    health_score = stats.get("health_score", "\u2014")
    contradiction_count = stats.get("contradiction_count", 0)
    cluster_count = stats.get("cluster_count", 0)
    recent = stats.get("recent_memories", []) or []
    mermaid_src = stats.get("entity_graph_mermaid", "")
    version = stats.get("version", "dev")

    # Build stat cards
    contra_color = "red" if contradiction_count else "green"
    cluster_color = "purple" if cluster_count else "green"
    health_color = "yellow" if health_score != "\u2014" else "dim"

    cards_html = "".join([
        _card("Memories", str(memory_count), "active memories", "blue"),
        _card("Entities", str(entity_count),
              f"{rel_count} relationships", "green"),
        _card("Health", str(health_score), "overall score", health_color),
        _card("Contradictions", str(contradiction_count),
              "detected", contra_color),
        _card("Consolidation", str(cluster_count),
              "similar clusters", cluster_color),
    ])

    # Recent memories rows for server-rendered initial data
    mem_rows = ""
    for m in recent[:10]:
        date = html.escape(str(m.get("date", ""))[:10])
        cat = html.escape(str(m.get("category", "")))
        raw_tags = m.get("tags", "")
        if isinstance(raw_tags, list):
            tags_str = ", ".join(str(t) for t in raw_tags)
        else:
            tags_str = str(raw_tags)
        tags = html.escape(tags_str)
        content = html.escape(str(m.get("content", ""))[:120])
        mem_rows += f"""
            <tr>
              <td class="cell-date">{date}</td>
              <td class="cell-cat"><span class="badge badge--blue">{cat}</span></td>
              <td class="cell-content">{content}</td>
              <td class="cell-tags">{tags}</td>
            </tr>"""

    # JSON-safe initial data for JS — escape </ sequences to prevent
    # script injection when embedded inside <script> tags.
    initial_data = json.dumps({
        "memory_count": memory_count,
        "entity_count": entity_count,
        "relationship_count": rel_count,
        "health_score": str(health_score),
        "contradiction_count": contradiction_count,
        "cluster_count": cluster_count,
        "recent_memories": recent[:10],
        "entity_graph_mermaid": mermaid_src,
        "version": version,
    }, default=str, ensure_ascii=True)
    # Escape characters that could break out of <script> context
    initial_data = initial_data.replace("<", "\\u003c").replace(">", "\\u003e")

    esc_version = html.escape(str(version))
    esc_mermaid = html.escape(mermaid_src) if mermaid_src else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tessera Dashboard</title>
<style>
/* ===== Claudel Design System — Data Cockpit ===== */
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=DM+Sans:wght@300;400;500;600;700&family=Fira+Code:wght@400;500&display=swap');
:root {{
  --bg: #09090B;
  --surface: #18181B;
  --surface-2: #27272A;
  --text: #FAFAFA;
  --text-muted: #A1A1AA;
  --text-dim: #71717A;
  --border: #27272A;
  --primary: #6366F1;
  --primary-soft: rgba(99,102,241,0.12);
  --accent: #22D3EE;
  --accent-soft: rgba(34,211,238,0.10);
  --blue: #6366F1;
  --blue-soft: rgba(99,102,241,0.12);
  --green: #16A34A;
  --yellow: #F59E0B;
  --red: #DC2626;
  --purple: #8B5CF6;
  --radius: 2px;
  --font: 'DM Sans', 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif;
  --font-heading: 'Space Grotesk', 'Pretendard', sans-serif;
  --font-mono: 'Fira Code', 'SF Mono', monospace;
}}

/* ===== Reset & Base ===== */
*, *::before, *::after {{ margin: 0; padding: 0; box-sizing: border-box; }}
html {{ scroll-behavior: smooth; }}
body {{
  background: var(--bg);
  font-family: var(--font);
  color: var(--text);
  min-height: 100vh;
  min-width: 375px;
  line-height: 1.5;
}}
a {{ color: var(--blue); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
button {{
  font-family: var(--font);
  cursor: pointer;
  border: none;
  border-radius: var(--radius);
  font-size: 13px;
  padding: 8px 14px;
  transition: background 0.15s, color 0.15s;
}}
button:hover {{ opacity: 0.88; }}
button:disabled {{ opacity: 0.4; cursor: not-allowed; }}
input, select {{
  font-family: var(--font);
  font-size: 13px;
  background: var(--surface);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 8px 12px;
  outline: none;
  transition: border-color 0.15s;
}}
input:focus, select:focus {{ border-color: var(--primary); }}

/* ===== Layout ===== */
.shell {{ max-width: 1280px; margin: 0 auto; padding: 0 24px 40px; }}

/* ===== Top Bar ===== */
.topbar {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 0;
  border-bottom: 1px solid var(--border);
  margin-bottom: 24px;
  flex-wrap: wrap;
  gap: 12px;
}}
.topbar-brand {{
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-heading);
  font-size: 17px;
  font-weight: 600;
  color: var(--text);
  white-space: nowrap;
  letter-spacing: -0.02em;
}}
.topbar-brand .diamond {{ color: var(--primary); }}
.topbar-nav {{
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}}
.topbar-nav a {{
  padding: 6px 14px;
  border-radius: var(--radius);
  font-size: 13px;
  font-weight: 500;
  color: var(--text-muted);
  transition: background 0.15s, color 0.15s;
}}
.topbar-nav a:hover {{ background: var(--surface); color: var(--text); text-decoration: none; }}
.topbar-nav a.active {{ background: var(--primary-soft); color: var(--primary); }}
.topbar-right {{
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  color: var(--text-dim);
}}

/* ===== Cards ===== */
.cards-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}}
.card {{
  background: var(--surface);
  border-radius: var(--radius);
  padding: 16px 20px;
  border: 1px solid var(--border);
}}
.card--blue .card-value {{ color: var(--primary); }}
.card--green .card-value {{ color: var(--green); }}
.card--yellow .card-value {{ color: var(--yellow); }}
.card--red .card-value {{ color: var(--red); }}
.card--purple .card-value {{ color: var(--purple); }}
.card--dim .card-value {{ color: var(--text-dim); }}
.card-label {{ color: var(--text-muted); font-size: 12px; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.05em; }}
.card-value {{ font-family: var(--font-heading); color: var(--text); font-size: 28px; font-weight: 600; letter-spacing: -0.02em; }}
.card-subtitle {{ color: var(--text-dim); font-size: 11px; margin-top: 2px; }}

/* ===== Panel ===== */
.panel {{
  background: var(--surface);
  border-radius: var(--radius);
  border: 1px solid var(--border);
  padding: 20px;
  margin-bottom: 16px;
}}
.panel-title {{
  font-family: var(--font-heading);
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 14px;
  color: var(--text);
  letter-spacing: -0.01em;
}}

/* ===== Tables ===== */
.tbl {{ width: 100%; border-collapse: collapse; }}
.tbl th {{
  text-align: left;
  padding: 10px 12px;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 2px solid var(--border);
}}
.tbl td {{ padding: 10px 12px; border-bottom: 1px solid var(--border); font-size: 14px; }}
.tbl tr:last-child td {{ border-bottom: none; }}
.tbl tr:hover td {{ background: rgba(255,255,255,0.02); }}
.cell-date {{ color: var(--text-muted); white-space: nowrap; }}
.cell-content {{ color: var(--text); max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.cell-tags {{ color: var(--text-dim); font-size: 12px; }}
.cell-cat {{ white-space: nowrap; }}

/* ===== Badges ===== */
.badge {{
  display: inline-block;
  padding: 2px 6px;
  border-radius: var(--radius);
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  font-family: var(--font-mono);
}}
.badge--blue {{ background: var(--blue-soft); color: var(--blue); }}
.badge--green {{ background: rgba(16,185,129,0.15); color: var(--green); }}
.badge--yellow {{ background: rgba(245,158,11,0.15); color: var(--yellow); }}
.badge--red {{ background: rgba(239,68,68,0.15); color: var(--red); }}
.badge--purple {{ background: rgba(139,92,246,0.15); color: var(--purple); }}
.badge--gray {{ background: rgba(100,116,139,0.15); color: var(--text-muted); }}

/* ===== Buttons ===== */
.btn-primary {{ background: var(--primary); color: #fff; }}
.btn-danger {{ background: var(--red); color: #fff; }}
.btn-ghost {{ background: transparent; color: var(--text-muted); border: 1px solid var(--border); }}
.btn-ghost:hover {{ background: var(--surface-2); color: var(--text); }}
.btn-sm {{ padding: 5px 10px; font-size: 12px; }}
.btn-group {{ display: flex; gap: 6px; flex-wrap: wrap; }}

/* ===== Filter Bar ===== */
.filter-bar {{
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 20px;
  align-items: center;
}}
.filter-bar input,
.filter-bar select {{ min-width: 120px; }}
.filter-bar input[type="text"] {{ flex: 1; min-width: 200px; }}

/* ===== Timeline ===== */
.timeline {{ position: relative; padding-left: 28px; }}
.timeline::before {{
  content: '';
  position: absolute;
  left: 8px;
  top: 0;
  bottom: 0;
  width: 2px;
  background: var(--border);
}}
.tl-date-header {{
  font-size: 13px;
  font-weight: 600;
  color: var(--text-muted);
  margin: 20px 0 10px;
  padding: 4px 0;
}}
.tl-item {{
  position: relative;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px 16px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: background 0.15s;
}}
.tl-item:hover {{ background: var(--surface-2); }}
.tl-item::before {{
  content: '';
  position: absolute;
  left: -24px;
  top: 18px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--primary);
}}
.tl-item.type-decision::before {{ background: var(--yellow); }}
.tl-item.type-document::before {{ background: var(--text-dim); }}
.tl-item .tl-preview {{ color: var(--text); font-size: 14px; }}
.tl-item .tl-meta {{ color: var(--text-dim); font-size: 12px; margin-top: 6px; display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }}
.tl-item .tl-full {{ display: none; margin-top: 12px; color: var(--text); font-size: 13px; white-space: pre-wrap; }}
.tl-item.expanded .tl-full {{ display: block; }}
.tl-item .tl-entities {{ display: flex; gap: 4px; flex-wrap: wrap; margin-top: 8px; }}
.tl-item .tl-entities .entity-badge {{
  font-size: 10px; padding: 2px 6px; border-radius: var(--radius);
  background: var(--primary-soft); color: var(--primary); border: 1px solid rgba(99,102,241,0.2);
  font-family: var(--font-mono);
}}
.tl-item .tl-related {{
  display: none; margin-top: 12px; padding: 10px; background: var(--bg);
  border-radius: var(--radius); border: 1px solid var(--border);
}}
.tl-item.expanded .tl-related {{ display: block; }}
.tl-related-title {{ font-size: 12px; color: var(--purple); font-weight: 600; margin-bottom: 8px; }}
.tl-related-item {{
  font-size: 12px; color: var(--text-muted); padding: 4px 0;
  border-bottom: 1px solid var(--border); cursor: pointer;
}}
.tl-related-item:last-child {{ border-bottom: none; }}
.tl-related-item:hover {{ color: var(--text); }}
.tl-related-shared {{ color: var(--text-dim); font-size: 11px; }}
.tl-contradiction {{
  margin-top: 8px; padding: 8px 12px; border-radius: var(--radius);
  background: rgba(220,38,38,0.08); border: 1px solid rgba(220,38,38,0.2);
  font-size: 12px; color: var(--red);
}}
.tl-contradiction a {{ color: var(--red); text-decoration: underline; cursor: pointer; }}
.tl-summary {{
  display: flex; gap: 16px; margin-bottom: 16px; font-size: 13px; color: var(--text-muted);
}}
.tl-summary span {{ font-weight: 600; color: var(--text); }}

/* ===== Insights ===== */
.insights-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 16px;
}}
.period-selector {{
  display: flex;
  gap: 4px;
  margin-bottom: 20px;
}}
.period-selector button {{
  padding: 6px 14px;
  border-radius: 6px;
  background: var(--surface);
  color: var(--text-muted);
}}
.period-selector button.active {{ background: var(--primary-soft); color: var(--primary); }}

/* ===== Manage ===== */
.batch-bar {{
  display: flex;
  gap: 8px;
  align-items: center;
  background: var(--surface);
  border: 1px solid var(--border);
  padding: 10px 16px;
  border-radius: var(--radius);
  margin-bottom: 16px;
  flex-wrap: wrap;
}}
.batch-bar.hidden {{ display: none; }}
.batch-bar .batch-count {{ font-size: 13px; color: var(--text-muted); margin-right: 8px; }}
.quick-actions {{
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 24px;
}}

/* ===== Checkbox ===== */
input[type="checkbox"] {{
  width: 16px;
  height: 16px;
  accent-color: var(--primary);
  cursor: pointer;
}}

/* ===== Scrollable ===== */
.scroll-x {{ overflow-x: auto; }}

/* ===== Chart container ===== */
.chart-box {{ position: relative; height: 260px; }}

/* ===== Mermaid ===== */
.mermaid-box {{
  background: var(--bg);
  border-radius: var(--radius);
  border: 1px solid var(--border);
  padding: 16px;
  overflow-x: auto;
  min-height: 80px;
}}

/* ===== Toast ===== */
.toast-container {{
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 8px;
}}
.toast {{
  padding: 10px 16px;
  border-radius: var(--radius);
  font-size: 13px;
  color: #fff;
  animation: toast-in 0.2s ease-out;
  max-width: 360px;
}}
.toast--success {{ background: var(--green); }}
.toast--error {{ background: var(--red); }}
.toast--info {{ background: var(--primary); }}
@keyframes toast-in {{
  from {{ opacity: 0; transform: translateY(12px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}

/* ===== Modal ===== */
.modal-overlay {{
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 8000;
  animation: fade-in 0.15s;
}}
.modal-overlay.hidden {{ display: none; }}
.modal {{
  background: var(--surface);
  border-radius: var(--radius);
  border: 1px solid var(--border);
  padding: 24px;
  width: 90%;
  max-width: 520px;
  max-height: 80vh;
  overflow-y: auto;
}}
.modal h3 {{ margin-bottom: 16px; font-size: 18px; }}
.modal label {{ display: block; font-size: 13px; color: var(--text-muted); margin: 12px 0 4px; }}
.modal textarea, .modal input[type="text"] {{
  width: 100%;
  font-family: var(--font);
  font-size: 13px;
  background: var(--bg);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 10px;
  outline: none;
  resize: vertical;
}}
.modal textarea {{ min-height: 100px; }}
.modal .modal-actions {{ display: flex; gap: 8px; justify-content: flex-end; margin-top: 20px; }}
@keyframes fade-in {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}

/* ===== Footer ===== */
.footer {{
  text-align: center;
  color: var(--text-dim);
  font-size: 12px;
  margin-top: 40px;
  padding: 20px 0;
  border-top: 1px solid var(--border);
}}

/* ===== Spinner ===== */
.spinner {{
  display: inline-block;
  width: 18px;
  height: 18px;
  border: 2px solid var(--border);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}}
@keyframes spin {{ to {{ transform: rotate(360deg); }} }}

/* ===== Empty State ===== */
.empty-state {{
  text-align: center;
  padding: 48px 16px;
  color: var(--text-dim);
  font-size: 14px;
}}

/* ===== View visibility ===== */
.view {{ display: none; }}
.view.active {{ display: block; }}

/* ===== Responsive ===== */
@media (max-width: 640px) {{
  .topbar {{ flex-direction: column; align-items: flex-start; }}
  .topbar-right {{ display: none; }}
  .cards-grid {{ grid-template-columns: repeat(2, 1fr); }}
  .insights-grid {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>

<!-- ===== Top Bar ===== -->
<div class="shell">
  <header class="topbar">
    <div class="topbar-brand">
      <span class="diamond">&#9670;</span> Tessera Dashboard
    </div>
    <nav class="topbar-nav" id="mainNav">
      <a href="#overview" data-view="overview" class="active">Overview</a>
      <a href="#timeline" data-view="timeline">Timeline</a>
      <a href="#graph" data-view="graph">Graph</a>
      <a href="#insights" data-view="insights">Insights</a>
      <a href="#manage" data-view="manage">Manage</a>
    </nav>
    <div class="topbar-right">
      <a href="/docs">API Docs</a>
      <span style="color:var(--border)">|</span>
      <span>v{esc_version}</span>
    </div>
  </header>

  <!-- ===== View: Overview ===== -->
  <section class="view active" id="view-overview">
    <div class="cards-grid">{cards_html}</div>

    <div class="panel">
      <div class="panel-title">Memory Growth</div>
      <div class="chart-box"><canvas id="growthChart"></canvas></div>
      <div id="growthFallback" style="display:none"></div>
    </div>

    <div class="panel">
      <div class="panel-title">Recent Memories</div>
      <div class="scroll-x">
        <table class="tbl" id="recentTable">
          <thead>
            <tr>
              <th>Date</th>
              <th>Category</th>
              <th>Content</th>
              <th>Tags</th>
            </tr>
          </thead>
          <tbody id="recentBody">{mem_rows}</tbody>
        </table>
      </div>
      <div id="recentFooter" style="color:var(--text-dim);margin-top:12px;font-size:13px">
        {"Showing " + str(len(recent[:10])) + " of " + str(memory_count) + " memories" if recent else "No memories yet"}
      </div>
    </div>

    <div class="panel" id="graphPanel" {"" if mermaid_src else 'style="display:none"'}>
      <div class="panel-title">Entity Knowledge Graph</div>
      <div class="mermaid-box">
        <div class="mermaid" id="mermaidGraph">{esc_mermaid}</div>
      </div>
    </div>
  </section>

  <!-- ===== View: Timeline ===== -->
  <section class="view" id="view-timeline">
    <div class="filter-bar">
      <input type="text" id="tlSearch" placeholder="Search memories..." onkeydown="if(event.key==='Enter')loadTimeline(true)">
      <input type="date" id="tlFrom" title="From date">
      <input type="date" id="tlTo" title="To date">
      <select id="tlType">
        <option value="">All types</option>
        <option value="memory">Memory</option>
        <option value="decision">Decision</option>
        <option value="document">Document</option>
      </select>
      <select id="tlCategory"><option value="">All categories</option></select>
      <select id="tlTag"><option value="">All tags</option></select>
      <button class="btn-primary btn-sm" onclick="loadTimeline(true)">Search</button>
    </div>
    <div id="tlSummary" class="tl-summary"></div>
    <div id="timelineContent" class="timeline"></div>
    <div style="text-align:center;margin-top:20px">
      <button class="btn-ghost" id="tlLoadMore" onclick="loadTimeline(false)" style="display:none">Load more</button>
    </div>
  </section>

  <!-- ===== View: Insights ===== -->
  <section class="view" id="view-insights">
    <div class="period-selector" id="periodSelector">
      <button data-days="7" class="active">7d</button>
      <button data-days="30">30d</button>
      <button data-days="90">90d</button>
      <button data-days="0">All</button>
    </div>
    <div class="insights-grid">
      <div class="panel">
        <div class="panel-title">Trending Topics</div>
        <div id="trendingTopics"><div class="empty-state">Loading...</div></div>
      </div>
      <div class="panel">
        <div class="panel-title">Decision Patterns</div>
        <div id="decisionPatterns"><div class="empty-state">Loading...</div></div>
      </div>
      <div class="panel">
        <div class="panel-title">Category Distribution</div>
        <div class="chart-box"><canvas id="categoryChart"></canvas></div>
        <div id="categoryFallback" style="display:none"></div>
      </div>
      <div class="panel">
        <div class="panel-title">Health Distribution</div>
        <div class="chart-box"><canvas id="healthChart"></canvas></div>
        <div id="healthFallback" style="display:none"></div>
      </div>
      <div class="panel">
        <div class="panel-title">Tag Frequency</div>
        <div class="chart-box"><canvas id="tagChart"></canvas></div>
        <div id="tagFallback" style="display:none"></div>
      </div>
      <div class="panel">
        <div class="panel-title">Confidence Distribution</div>
        <div class="chart-box"><canvas id="confidenceChart"></canvas></div>
        <div id="confidenceFallback" style="display:none"></div>
      </div>
    </div>
  </section>

  <!-- ===== View: Manage ===== -->
  <section class="view" id="view-manage">
    <div class="filter-bar">
      <input type="text" id="mgSearch" placeholder="Search...">
      <select id="mgCategory"><option value="">All categories</option></select>
      <select id="mgTag"><option value="">All tags</option></select>
      <select id="mgSort">
        <option value="date">Sort by date</option>
        <option value="category">Sort by category</option>
      </select>
      <button class="btn-primary btn-sm" onclick="loadManageTable()">Filter</button>
    </div>

    <div class="batch-bar hidden" id="batchBar">
      <span class="batch-count" id="batchCount">0 selected</span>
      <button class="btn-ghost btn-sm" onclick="batchChangeTags()">Change Tags</button>
      <button class="btn-ghost btn-sm" onclick="batchChangeCategory()">Change Category</button>
      <button class="btn-danger btn-sm" onclick="batchDelete()">Delete Selected</button>
      <button class="btn-ghost btn-sm" onclick="batchMerge()">Merge</button>
      <button class="btn-ghost btn-sm" onclick="batchProvenance()">View Provenance</button>
    </div>

    <div class="scroll-x">
      <table class="tbl" id="manageTable">
        <thead>
          <tr>
            <th><input type="checkbox" id="selectAll" onchange="toggleSelectAll()"></th>
            <th>Date</th>
            <th>Category</th>
            <th>Content</th>
            <th>Tags</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody id="manageBody"></tbody>
      </table>
    </div>
    <div id="manageFooter" style="text-align:center;margin-top:16px"></div>

    <div class="panel" style="margin-top:24px">
      <div class="panel-title">Quick Actions</div>
      <div class="quick-actions">
        <button class="btn-primary" onclick="quickAction('/auto-curate','POST','Auto-curate complete')">Auto-Curate</button>
        <button class="btn-primary" onclick="quickAction('/retention-policy','POST','Retention policy applied')">Retention Policy</button>
        <button class="btn-primary" onclick="quickAction('/sleep-consolidate','POST','Sleep consolidation complete')">Sleep Consolidation</button>
        <button class="btn-ghost" onclick="openNewMemoryModal()">+ New Memory</button>
      </div>
    </div>
  </section>

  <!-- ===== View: Knowledge Graph ===== -->
  <section class="view" id="view-graph">
    <div class="panel" style="padding:0;overflow:hidden;position:relative">
      <div style="display:flex;align-items:center;justify-content:space-between;padding:16px 20px;border-bottom:1px solid var(--border)">
        <div style="display:flex;align-items:center;gap:12px">
          <span class="panel-title" style="margin:0">Knowledge Graph</span>
          <span id="graphStats" style="color:var(--text-dim);font-size:13px"></span>
        </div>
        <div style="display:flex;gap:8px;align-items:center">
          <input type="text" id="graphSearch" placeholder="Search entities..."
            style="padding:6px 12px;background:var(--surface-2);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:13px;width:180px"
            oninput="filterGraph()">
          <select id="graphTypeFilter" onchange="filterGraph()"
            style="padding:6px 10px;background:var(--surface-2);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:13px">
            <option value="">All types</option>
            <option value="person">Person</option>
            <option value="technology">Technology</option>
            <option value="project">Project</option>
            <option value="organization">Organization</option>
            <option value="concept">Concept</option>
            <option value="location">Location</option>
          </select>
          <button class="btn-ghost" onclick="resetGraphView()" title="Reset view">Reset</button>
        </div>
      </div>
      <div id="graphCanvas" style="width:100%;height:70vh;background:var(--bg)"></div>
      <div id="graphDetail" style="display:none;position:absolute;top:60px;right:16px;width:300px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:16px;box-shadow:0 8px 32px rgba(0,0,0,0.4);z-index:10;max-height:calc(70vh - 60px);overflow-y:auto">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
          <h3 id="detailName" style="font-size:15px;font-weight:600"></h3>
          <button onclick="document.getElementById('graphDetail').style.display='none'" style="background:none;color:var(--text-muted);font-size:18px;padding:0 4px">&times;</button>
        </div>
        <div id="detailType" style="margin-bottom:8px"></div>
        <div id="detailMentions" style="color:var(--text-muted);font-size:13px;margin-bottom:12px"></div>
        <div id="detailRelations"></div>
      </div>
    </div>
    <div style="display:flex;gap:12px;margin-top:16px;flex-wrap:wrap">
      <div style="display:flex;align-items:center;gap:6px;font-size:12px;color:var(--text-dim)">
        <span style="display:inline-block;width:8px;height:8px;border-radius:1px;background:#6366F1"></span> Person
        <span style="display:inline-block;width:8px;height:8px;border-radius:1px;background:#22D3EE;margin-left:8px"></span> Technology
        <span style="display:inline-block;width:8px;height:8px;border-radius:1px;background:#F59E0B;margin-left:8px"></span> Project
        <span style="display:inline-block;width:8px;height:8px;border-radius:1px;background:#8B5CF6;margin-left:8px"></span> Organization
        <span style="display:inline-block;width:8px;height:8px;border-radius:1px;background:#DC2626;margin-left:8px"></span> Concept
        <span style="display:inline-block;width:8px;height:8px;border-radius:1px;background:#16A34A;margin-left:8px"></span> Location
        <span style="display:inline-block;width:8px;height:8px;border-radius:1px;background:#71717A;margin-left:8px"></span> Other
      </div>
    </div>
  </section>

  <footer class="footer">
    Tessera v{esc_version} &mdash;
    <a href="https://github.com/besslframework-stack/project-tessera">GitHub</a>
  </footer>
</div>

<!-- ===== Toast Container ===== -->
<div class="toast-container" id="toastContainer"></div>

<!-- ===== Modal: Edit Memory ===== -->
<div class="modal-overlay hidden" id="editModal">
  <div class="modal">
    <h3 id="editModalTitle">Edit Memory</h3>
    <input type="hidden" id="editId">
    <label>Content</label>
    <textarea id="editContent"></textarea>
    <label>Tags (comma-separated)</label>
    <input type="text" id="editTags">
    <label>Category</label>
    <input type="text" id="editCategory">
    <div class="modal-actions">
      <button class="btn-ghost" onclick="closeModal('editModal')">Cancel</button>
      <button class="btn-primary" onclick="saveEdit()">Save</button>
    </div>
  </div>
</div>

<!-- ===== Modal: New Memory ===== -->
<div class="modal-overlay hidden" id="newModal">
  <div class="modal">
    <h3>New Memory</h3>
    <label>Content</label>
    <textarea id="newContent"></textarea>
    <label>Tags (comma-separated)</label>
    <input type="text" id="newTags">
    <label>Category</label>
    <input type="text" id="newCategory" value="general">
    <div class="modal-actions">
      <button class="btn-ghost" onclick="closeModal('newModal')">Cancel</button>
      <button class="btn-primary" onclick="saveNew()">Create</button>
    </div>
  </div>
</div>

<!-- ===== Modal: Confirm Delete ===== -->
<div class="modal-overlay hidden" id="deleteModal">
  <div class="modal">
    <h3>Confirm Delete</h3>
    <p style="color:var(--text-muted);margin-bottom:16px" id="deleteMsg">Delete this memory? This cannot be undone.</p>
    <div class="modal-actions">
      <button class="btn-ghost" onclick="closeModal('deleteModal')">Cancel</button>
      <button class="btn-danger" id="deleteConfirmBtn" onclick="confirmDelete()">Delete</button>
    </div>
  </div>
</div>

<!-- ===== CDN Scripts (async to avoid blocking) ===== -->
<script async src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"
  onload="window._chartjsReady=true" onerror="window._chartjsFailed=true"></script>
<script async src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"
  onload="window._mermaidReady=true" onerror="window._mermaidFailed=true"></script>
<script async src="https://cdn.jsdelivr.net/npm/cytoscape@3/dist/cytoscape.min.js"
  onload="window._cytoscapeReady=true" onerror="window._cytoscapeFailed=true"></script>

<script>
"use strict";

/* ---------- Initial Data ---------- */
const INITIAL = {initial_data};
let chartjsReady = false;

/* ---------- State ---------- */
let tlOffset = 0;
const TL_LIMIT = 20;
let mgPage = 0;
const MG_LIMIT = 50;
let selectedIds = new Set();
let deleteQueue = [];
let insightPeriod = 7;
let refreshInterval = null;

/* ---------- API Helper ---------- */
async function api(path, options = {{}}) {{
  try {{
    const res = await fetch(path, {{
      ...options,
      headers: {{
        'Content-Type': 'application/json',
        ...(options.headers || {{}})
      }}
    }});
    if (!res.ok) {{
      const err = await res.json().catch(() => ({{}}));
      throw new Error(err.detail || res.statusText);
    }}
    const json = await res.json();
    return json.data !== undefined ? json.data : json;
  }} catch (e) {{
    console.error('API error:', path, e);
    throw e;
  }}
}}

/* ---------- Toast ---------- */
function toast(msg, type = 'info') {{
  const el = document.createElement('div');
  el.className = 'toast toast--' + type;
  el.textContent = msg;
  document.getElementById('toastContainer').appendChild(el);
  setTimeout(() => el.remove(), 4000);
}}

/* ---------- Modal Helpers ---------- */
function openModal(id) {{ document.getElementById(id).classList.remove('hidden'); }}
function closeModal(id) {{ document.getElementById(id).classList.add('hidden'); }}

document.querySelectorAll('.modal-overlay').forEach(ov => {{
  ov.addEventListener('click', e => {{
    if (e.target === ov) ov.classList.add('hidden');
  }});
}});

/* ---------- Router ---------- */
function navigate(hash) {{
  const view = (hash || '#overview').replace('#', '') || 'overview';
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  const target = document.getElementById('view-' + view);
  if (target) target.classList.add('active');
  else document.getElementById('view-overview').classList.add('active');

  document.querySelectorAll('#mainNav a').forEach(a => {{
    a.classList.toggle('active', a.dataset.view === view);
  }});

  // Lazy-load view data
  if (view === 'timeline') {{ restoreTimelineFilters(); loadTimeline(true); }}
  if (view === 'graph') loadGraph();
  if (view === 'insights') loadInsights();
  if (view === 'manage') loadManageTable();
  if (view === 'overview') startAutoRefresh();
  else stopAutoRefresh();
}}

window.addEventListener('hashchange', () => navigate(location.hash));

/* ---------- Escape ---------- */
function esc(s) {{
  const d = document.createElement('div');
  d.textContent = s == null ? '' : String(s);
  return d.innerHTML;
}}

/* ========================================
   VIEW: OVERVIEW
   ======================================== */

let growthChart = null;

function startAutoRefresh() {{
  stopAutoRefresh();
  refreshInterval = setInterval(refreshOverview, 30000);
}}
function stopAutoRefresh() {{
  if (refreshInterval) {{ clearInterval(refreshInterval); refreshInterval = null; }}
}}

async function refreshOverview() {{
  try {{
    const data = await api('/knowledge-stats');
    if (data && typeof data === 'object') {{
      updateGrowthChart(data);
    }}
  }} catch (_) {{}}
}}

function updateGrowthChart(data) {{
  if (!chartjsReady) return;
  const labels = data.weekly_labels || data.labels || [];
  const values = data.weekly_counts || data.counts || [];
  if (!labels.length) return;

  const ctx = document.getElementById('growthChart');
  if (!ctx) return;

  if (growthChart) growthChart.destroy();
  growthChart = new Chart(ctx, {{
    type: 'line',
    data: {{
      labels: labels,
      datasets: [{{
        label: 'Memories',
        data: values,
        borderColor: '#3b82f6',
        backgroundColor: 'rgba(59,130,246,0.1)',
        fill: true,
        tension: 0.3,
        pointRadius: 3,
        pointBackgroundColor: '#3b82f6'
      }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{
        legend: {{ display: false }},
      }},
      scales: {{
        x: {{
          grid: {{ color: 'rgba(51,65,85,0.5)' }},
          ticks: {{ color: '#94a3b8', font: {{ size: 11 }} }}
        }},
        y: {{
          beginAtZero: true,
          grid: {{ color: 'rgba(51,65,85,0.5)' }},
          ticks: {{ color: '#94a3b8', font: {{ size: 11 }} }}
        }}
      }}
    }}
  }});
}}

function showGrowthFallback(data) {{
  const fb = document.getElementById('growthFallback');
  const cv = document.getElementById('growthChart');
  if (cv) cv.style.display = 'none';
  fb.style.display = 'block';
  const labels = data.weekly_labels || data.labels || [];
  const values = data.weekly_counts || data.counts || [];
  if (!labels.length) {{
    fb.innerHTML = '<div class="empty-state">No growth data available</div>';
    return;
  }}
  let rows = labels.map((l, i) =>
    '<tr><td class="cell-date">' + esc(l) + '</td><td>' + (values[i] || 0) + '</td></tr>'
  ).join('');
  fb.innerHTML = '<table class="tbl"><thead><tr><th>Week</th><th>Count</th></tr></thead><tbody>' + rows + '</tbody></table>';
}}

/* ========================================
   VIEW: TIMELINE
   ======================================== */

function saveTimelineFilters() {{
  const f = {{
    q: document.getElementById('tlSearch').value,
    from: document.getElementById('tlFrom').value,
    to: document.getElementById('tlTo').value,
    type: document.getElementById('tlType').value,
    cat: document.getElementById('tlCategory').value,
    tag: document.getElementById('tlTag').value,
  }};
  const p = new URLSearchParams();
  Object.entries(f).forEach(([k,v]) => {{ if (v) p.set(k, v); }});
  const qs = p.toString();
  const newHash = '#timeline' + (qs ? '?' + qs : '');
  if (location.hash !== newHash) history.replaceState(null, '', newHash);
}}

function restoreTimelineFilters() {{
  const hash = location.hash.replace('#timeline', '');
  if (!hash.startsWith('?')) return;
  const p = new URLSearchParams(hash.slice(1));
  if (p.get('q')) document.getElementById('tlSearch').value = p.get('q');
  if (p.get('from')) document.getElementById('tlFrom').value = p.get('from');
  if (p.get('to')) document.getElementById('tlTo').value = p.get('to');
  if (p.get('type')) document.getElementById('tlType').value = p.get('type');
  if (p.get('cat')) document.getElementById('tlCategory').value = p.get('cat');
  if (p.get('tag')) document.getElementById('tlTag').value = p.get('tag');
}}

function renderTimelineItem(item) {{
  const rtype = item.type || item.record_type || item.category || 'memory';
  const cls = rtype === 'decision' ? 'type-decision' : rtype === 'document' ? 'type-document' : '';
  const icon = rtype === 'decision' ? '&#9670;' : rtype === 'document' ? '&#9680;' : '&#9679;';
  const itemId = item.id || '';

  const tags = (Array.isArray(item.tags) ? item.tags :
    typeof item.tags === 'string' ? item.tags.replace(/[\\[\\]]/g,'').split(',').map(s=>s.trim()).filter(Boolean) : []
  ).map(t => '<span class="badge badge--gray">' + esc(t) + '</span>').join(' ');

  const content = esc(String(item.content || '').slice(0, 150));
  const full = esc(String(item.content || ''));

  // Entity badges
  const entities = (item.entities || []);
  const entBadges = entities.length
    ? '<div class="tl-entities">' + entities.map(e => '<span class="entity-badge">' + esc(e) + '</span>').join('') + '</div>'
    : '';

  // Related records
  const related = item.related || [];
  let relatedHtml = '';
  if (related.length) {{
    const relItems = related.map(r =>
      '<div class="tl-related-item" onclick="event.stopPropagation();scrollToRecord(\\\'' + esc(r.id || '') + '\\\')">' +
      esc(r.content_preview || '') +
      '<div class="tl-related-shared">shared: ' + (r.shared_entities || []).map(e => esc(e)).join(', ') + '</div></div>'
    ).join('');
    relatedHtml = '<div class="tl-related"><div class="tl-related-title">&#9734; Related Records (' + related.length + ')</div>' + relItems + '</div>';
  }}

  // Contradiction warning
  const contra = item.contradiction;
  let contraHtml = '';
  if (contra) {{
    contraHtml = '<div class="tl-contradiction">&#9888; Contradicts: <a onclick="event.stopPropagation();scrollToRecord(\\\'' +
      esc(contra.conflicting_id || '') + '\\\')">' + esc(contra.content_preview || '') + '</a></div>';
  }}

  return `<div class="tl-item ${{cls}}" data-id="${{esc(itemId)}}" onclick="this.classList.toggle('expanded')">
    <div class="tl-preview">${{icon}} ${{content}}</div>
    <div class="tl-meta">${{esc(rtype)}} ${{tags}}</div>
    ${{entBadges}}
    ${{contraHtml}}
    <div class="tl-full">${{full}}</div>
    ${{relatedHtml}}
  </div>`;
}}

function scrollToRecord(id) {{
  if (!id) return;
  const el = document.querySelector('[data-id="' + CSS.escape(id) + '"]');
  if (el) {{
    el.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
    el.classList.add('expanded');
    el.style.outline = '2px solid var(--blue)';
    setTimeout(() => el.style.outline = '', 2000);
  }}
}}

async function loadTimeline(reset) {{
  if (reset) {{ tlOffset = 0; document.getElementById('timelineContent').innerHTML = ''; }}
  saveTimelineFilters();

  const search = document.getElementById('tlSearch').value.trim();
  const from = document.getElementById('tlFrom').value;
  const to = document.getElementById('tlTo').value;
  const type = document.getElementById('tlType').value;
  const cat = document.getElementById('tlCategory').value;
  const tag = document.getElementById('tlTag').value;

  const container = document.getElementById('timelineContent');
  const summary = document.getElementById('tlSummary');

  try {{
    if (search) {{
      /* Search mode — uses /recall endpoint */
      const result = await api('/recall', {{
        method: 'POST',
        body: JSON.stringify({{ query: search, top_k: TL_LIMIT,
          since: from || undefined, until: to || undefined,
          category: cat || undefined }})
      }});
      const items = Array.isArray(result) ? result : (result.results || []);

      if (!items.length && reset) {{
        container.innerHTML = '<div class="empty-state">No records matching "' + esc(search) + '"</div>';
        summary.innerHTML = '';
        document.getElementById('tlLoadMore').style.display = 'none';
        return;
      }}

      summary.innerHTML = 'Found <span>' + items.length + '</span> results for "' + esc(search) + '"';

      let currentDate = '';
      items.forEach(item => {{
        const d = String(item.date || '').slice(0, 10);
        if (d !== currentDate) {{
          currentDate = d;
          container.innerHTML += '<div class="tl-date-header">' + esc(d || 'Unknown date') + '</div>';
        }}
        container.innerHTML += renderTimelineItem(item);
      }});

      document.getElementById('tlLoadMore').style.display = 'none';

    }} else {{
      /* Browse mode — uses /memories/timeline endpoint */
      const params = new URLSearchParams({{ offset: tlOffset, limit: TL_LIMIT }});
      if (from) params.set('since', from);
      if (to) params.set('until', to);
      if (type) params.set('record_type', type);
      if (cat) params.set('category', cat);
      if (tag) params.set('tag', tag);

      const result = await api('/memories/timeline?' + params.toString());

      /* Handle grouped date format: {{dates: [{{date, records: [...]}}], total_records, total_dates}} */
      const dates = result.dates || [];
      const totalRecords = result.total_records || 0;
      const totalDates = result.total_dates || 0;

      if (!dates.length && reset) {{
        container.innerHTML = '<div class="empty-state">No records found</div>';
        summary.innerHTML = '';
        document.getElementById('tlLoadMore').style.display = 'none';
        return;
      }}

      if (reset) {{
        summary.innerHTML = '<span>' + totalRecords + '</span> records across <span>' + totalDates + '</span> days';
      }}

      let recordCount = 0;
      dates.forEach(dateGroup => {{
        container.innerHTML += '<div class="tl-date-header">' + esc(dateGroup.date || '') + '</div>';
        (dateGroup.records || []).forEach(item => {{
          container.innerHTML += renderTimelineItem(item);
          recordCount++;
        }});
      }});

      tlOffset += dates.length;
      document.getElementById('tlLoadMore').style.display =
        dates.length >= TL_LIMIT ? 'inline-block' : 'none';
    }}
  }} catch (e) {{
    if (reset) container.innerHTML = '<div class="empty-state">Error loading timeline: ' + esc(e.message) + '</div>';
    else toast('Error: ' + e.message, 'error');
  }}
}}

/* Load available tags for filter dropdowns */
async function loadTagOptions() {{
  try {{
    const tags = await api('/memories/tags');
    const tagsList = Array.isArray(tags) ? tags : (tags.tags || []);
    const selectors = ['tlTag', 'mgTag'];
    selectors.forEach(id => {{
      const sel = document.getElementById(id);
      if (!sel) return;
      tagsList.forEach(t => {{
        const o = document.createElement('option');
        o.value = typeof t === 'string' ? t : t.tag || t.name || '';
        o.textContent = o.value;
        sel.appendChild(o);
      }});
    }});
  }} catch (_) {{}}
}}

async function loadCategoryOptions() {{
  try {{
    const cats = await api('/memories/categories');
    const catList = Array.isArray(cats) ? cats : (cats.categories || []);
    const selectors = ['mgCategory', 'tlCategory'];
    selectors.forEach(id => {{
      const sel = document.getElementById(id);
      if (!sel) return;
      catList.forEach(c => {{
        const o = document.createElement('option');
        o.value = typeof c === 'string' ? c : c.category || c.name || '';
        o.textContent = o.value;
        sel.appendChild(o);
      }});
    }});
  }} catch (_) {{}}
}}

/* ========================================
   VIEW: INSIGHTS
   ======================================== */

async function loadInsights() {{
  const days = insightPeriod;
  const sinceParam = days > 0 ? '?days=' + days : '';

  const [trending, decisions, categories, health, tagsData, confidence] = await Promise.allSettled([
    api('/auto-insights' + sinceParam),
    api('/decision-timeline' + sinceParam),
    api('/memories/categories'),
    api('/memory-health'),
    api('/memories/tags'),
    api('/memory-confidence')
  ]);

  // Trending
  const tEl = document.getElementById('trendingTopics');
  if (trending.status === 'fulfilled' && trending.value) {{
    const items = Array.isArray(trending.value) ? trending.value
      : (trending.value.topics || trending.value.insights || []);
    if (items.length) {{
      tEl.innerHTML = '<ul style="list-style:none;padding:0">' +
        items.slice(0, 10).map(i => {{
          const text = typeof i === 'string' ? i : (i.topic || i.title || i.insight || JSON.stringify(i));
          return '<li style="padding:8px 0;border-bottom:1px solid var(--border);font-size:14px">' + esc(text) + '</li>';
        }}).join('') + '</ul>';
    }} else tEl.innerHTML = '<div class="empty-state">No trending topics</div>';
  }} else tEl.innerHTML = '<div class="empty-state">Could not load</div>';

  // Decisions
  const dEl = document.getElementById('decisionPatterns');
  if (decisions.status === 'fulfilled' && decisions.value) {{
    const items = Array.isArray(decisions.value) ? decisions.value
      : (decisions.value.decisions || decisions.value.timeline || []);
    if (items.length) {{
      dEl.innerHTML = '<ul style="list-style:none;padding:0">' +
        items.slice(0, 10).map(i => {{
          const text = typeof i === 'string' ? i : (i.decision || i.content || i.title || JSON.stringify(i));
          const date = i.date || '';
          return '<li style="padding:8px 0;border-bottom:1px solid var(--border);font-size:14px">' +
            (date ? '<span class="cell-date" style="margin-right:8px">' + esc(String(date).slice(0,10)) + '</span>' : '') +
            esc(String(text).slice(0, 120)) + '</li>';
        }}).join('') + '</ul>';
    }} else dEl.innerHTML = '<div class="empty-state">No decisions recorded</div>';
  }} else dEl.innerHTML = '<div class="empty-state">Could not load</div>';

  // Category chart
  if (categories.status === 'fulfilled' && categories.value) {{
    const catData = Array.isArray(categories.value) ? categories.value
      : (categories.value.categories || []);
    renderCategoryChart(catData);
  }}

  // Health chart
  if (health.status === 'fulfilled' && health.value) {{
    renderHealthChart(health.value);
  }}

  // Tag frequency chart
  if (tagsData.status === 'fulfilled' && tagsData.value) {{
    renderTagChart(tagsData.value);
  }}

  // Confidence distribution
  if (confidence.status === 'fulfilled' && confidence.value) {{
    renderConfidenceChart(confidence.value);
  }}
}}

function renderCategoryChart(catData) {{
  const labels = catData.map(c => typeof c === 'string' ? c : (c.category || c.name || ''));
  const values = catData.map(c => typeof c === 'object' ? (c.count || c.total || 1) : 1);
  const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316'];

  if (!chartjsReady) {{
    const fb = document.getElementById('categoryFallback');
    const cv = document.getElementById('categoryChart');
    if (cv) cv.style.display = 'none';
    fb.style.display = 'block';
    fb.innerHTML = '<table class="tbl"><thead><tr><th>Category</th><th>Count</th></tr></thead><tbody>' +
      labels.map((l, i) => '<tr><td>' + esc(l) + '</td><td>' + values[i] + '</td></tr>').join('') +
      '</tbody></table>';
    return;
  }}

  const ctx = document.getElementById('categoryChart');
  if (!ctx) return;
  new Chart(ctx, {{
    type: 'doughnut',
    data: {{
      labels: labels,
      datasets: [{{
        data: values,
        backgroundColor: colors.slice(0, labels.length),
        borderWidth: 0
      }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{
        legend: {{
          position: 'right',
          labels: {{ color: '#94a3b8', font: {{ size: 11 }}, padding: 12 }}
        }}
      }}
    }}
  }});
}}

function renderHealthChart(healthData) {{
  const raw = typeof healthData === 'string' ? healthData : JSON.stringify(healthData);
  // Try to parse health distribution data
  let labels = [];
  let values = [];

  if (typeof healthData === 'object' && !Array.isArray(healthData)) {{
    // Could be {{"high": 10, "medium": 5, "low": 2}} or similar
    const keys = Object.keys(healthData).filter(k => typeof healthData[k] === 'number');
    if (keys.length) {{
      labels = keys;
      values = keys.map(k => healthData[k]);
    }} else if (healthData.distribution) {{
      const dist = healthData.distribution;
      labels = Object.keys(dist);
      values = Object.values(dist);
    }}
  }}

  if (!labels.length) {{
    const fb = document.getElementById('healthFallback');
    const cv = document.getElementById('healthChart');
    if (cv) cv.style.display = 'none';
    fb.style.display = 'block';
    fb.innerHTML = '<div class="empty-state" style="font-size:13px;white-space:pre-wrap">' + esc(raw.slice(0, 500)) + '</div>';
    return;
  }}

  const colors = {{ high: '#10b981', good: '#10b981', medium: '#f59e0b', warning: '#f59e0b', low: '#ef4444', critical: '#ef4444' }};

  if (!chartjsReady) {{
    const fb = document.getElementById('healthFallback');
    const cv = document.getElementById('healthChart');
    if (cv) cv.style.display = 'none';
    fb.style.display = 'block';
    fb.innerHTML = '<table class="tbl"><thead><tr><th>Level</th><th>Count</th></tr></thead><tbody>' +
      labels.map((l, i) => '<tr><td>' + esc(l) + '</td><td>' + values[i] + '</td></tr>').join('') +
      '</tbody></table>';
    return;
  }}

  const ctx = document.getElementById('healthChart');
  if (!ctx) return;
  new Chart(ctx, {{
    type: 'bar',
    data: {{
      labels: labels,
      datasets: [{{
        data: values,
        backgroundColor: labels.map(l => colors[l.toLowerCase()] || '#3b82f6'),
        borderWidth: 0,
        borderRadius: 4
      }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{
          grid: {{ display: false }},
          ticks: {{ color: '#94a3b8' }}
        }},
        y: {{
          beginAtZero: true,
          grid: {{ color: 'rgba(51,65,85,0.5)' }},
          ticks: {{ color: '#94a3b8' }}
        }}
      }}
    }}
  }});
}}

function renderTagChart(tagData) {{
  let labels = [], values = [];
  if (typeof tagData === 'object' && !Array.isArray(tagData)) {{
    // {{tag: count}} format
    const entries = Object.entries(tagData).sort((a, b) => b[1] - a[1]).slice(0, 15);
    labels = entries.map(e => e[0]);
    values = entries.map(e => e[1]);
  }} else if (Array.isArray(tagData)) {{
    labels = tagData.slice(0, 15).map(t => typeof t === 'string' ? t : (t.tag || t.name || ''));
    values = tagData.slice(0, 15).map(t => typeof t === 'object' ? (t.count || 1) : 1);
  }}

  if (!labels.length) {{
    document.getElementById('tagFallback').style.display = 'block';
    document.getElementById('tagFallback').innerHTML = '<div class="empty-state">No tag data</div>';
    const cv = document.getElementById('tagChart');
    if (cv) cv.style.display = 'none';
    return;
  }}

  if (!chartjsReady) {{
    const fb = document.getElementById('tagFallback');
    const cv = document.getElementById('tagChart');
    if (cv) cv.style.display = 'none';
    fb.style.display = 'block';
    fb.innerHTML = '<table class="tbl"><thead><tr><th>Tag</th><th>Count</th></tr></thead><tbody>' +
      labels.map((l, i) => '<tr><td>' + esc(l) + '</td><td>' + values[i] + '</td></tr>').join('') +
      '</tbody></table>';
    return;
  }}

  const ctx = document.getElementById('tagChart');
  if (!ctx) return;
  new Chart(ctx, {{
    type: 'bar',
    data: {{
      labels: labels,
      datasets: [{{ data: values, backgroundColor: '#3b82f6', borderWidth: 0, borderRadius: 4 }}]
    }},
    options: {{
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ beginAtZero: true, grid: {{ color: 'rgba(51,65,85,0.5)' }}, ticks: {{ color: '#94a3b8' }} }},
        y: {{ grid: {{ display: false }}, ticks: {{ color: '#94a3b8', font: {{ size: 11 }} }} }}
      }}
    }}
  }});
}}

function renderConfidenceChart(confData) {{
  let labels = [], values = [];
  const raw = typeof confData === 'string' ? confData : JSON.stringify(confData);

  if (typeof confData === 'object' && !Array.isArray(confData)) {{
    if (confData.distribution) {{
      const dist = confData.distribution;
      labels = Object.keys(dist);
      values = Object.values(dist);
    }} else {{
      const keys = Object.keys(confData).filter(k => typeof confData[k] === 'number');
      labels = keys;
      values = keys.map(k => confData[k]);
    }}
  }}

  if (!labels.length) {{
    const fb = document.getElementById('confidenceFallback');
    const cv = document.getElementById('confidenceChart');
    if (cv) cv.style.display = 'none';
    fb.style.display = 'block';
    fb.innerHTML = '<div class="empty-state" style="font-size:12px;white-space:pre-wrap">' + esc(raw.slice(0, 300)) + '</div>';
    return;
  }}

  const colors = {{ high: '#10b981', medium: '#f59e0b', low: '#ef4444' }};

  if (!chartjsReady) {{
    const fb = document.getElementById('confidenceFallback');
    const cv = document.getElementById('confidenceChart');
    if (cv) cv.style.display = 'none';
    fb.style.display = 'block';
    fb.innerHTML = '<table class="tbl"><thead><tr><th>Level</th><th>Count</th></tr></thead><tbody>' +
      labels.map((l, i) => '<tr><td>' + esc(l) + '</td><td>' + values[i] + '</td></tr>').join('') +
      '</tbody></table>';
    return;
  }}

  const ctx = document.getElementById('confidenceChart');
  if (!ctx) return;
  new Chart(ctx, {{
    type: 'bar',
    data: {{
      labels: labels,
      datasets: [{{
        data: values,
        backgroundColor: labels.map(l => colors[l.toLowerCase()] || '#8b5cf6'),
        borderWidth: 0,
        borderRadius: 4
      }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ grid: {{ display: false }}, ticks: {{ color: '#94a3b8' }} }},
        y: {{ beginAtZero: true, grid: {{ color: 'rgba(51,65,85,0.5)' }}, ticks: {{ color: '#94a3b8' }} }}
      }}
    }}
  }});
}}

// Period selector
document.getElementById('periodSelector').addEventListener('click', e => {{
  const btn = e.target.closest('button');
  if (!btn) return;
  insightPeriod = parseInt(btn.dataset.days);
  document.querySelectorAll('#periodSelector button').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  loadInsights();
}});

/* ========================================
   VIEW: MANAGE
   ======================================== */

async function loadManageTable() {{
  const search = document.getElementById('mgSearch').value.trim();
  const cat = document.getElementById('mgCategory').value;
  const tag = document.getElementById('mgTag').value;
  const sort = document.getElementById('mgSort').value;

  const body = document.getElementById('manageBody');
  body.innerHTML = '<tr><td colspan="6" class="empty-state"><span class="spinner"></span> Loading...</td></tr>';
  selectedIds.clear();
  updateBatchBar();

  try {{
    let items;
    if (search) {{
      const result = await api('/recall', {{
        method: 'POST',
        body: JSON.stringify({{ query: search, limit: MG_LIMIT }})
      }});
      items = Array.isArray(result) ? result : (result.results || []);
    }} else {{
      const params = new URLSearchParams({{ offset: 0, limit: MG_LIMIT }});
      if (cat) params.set('category', cat);
      if (tag) params.set('tag', tag);
      const result = await api('/memories/timeline?' + params.toString());
      /* Handle grouped date format from timeline API */
      if (result && result.dates) {{
        items = [];
        (result.dates || []).forEach(dg => {{
          (dg.records || []).forEach(r => {{
            if (!r.date) r.date = dg.date;
            items.push(r);
          }});
        }});
      }} else {{
        items = Array.isArray(result) ? result : (result.records || result.items || []);
      }}
    }}

    if (sort === 'category') {{
      items.sort((a, b) => (a.category || '').localeCompare(b.category || ''));
    }}

    if (!items.length) {{
      body.innerHTML = '<tr><td colspan="6" class="empty-state">No memories found</td></tr>';
      return;
    }}

    body.innerHTML = items.map(item => {{
      const id = item.id || item.memory_id || '';
      const date = String(item.date || item.created_at || '').slice(0, 10);
      const cat = item.category || '';
      const content = String(item.content || '').slice(0, 100);
      const tags = (Array.isArray(item.tags) ? item.tags :
        typeof item.tags === 'string' ? item.tags.replace(/[\\[\\]]/g,'').split(',').map(s=>s.trim()).filter(Boolean) : []).join(', ');
      return `<tr data-id="${{esc(id)}}">
        <td><input type="checkbox" class="row-check" value="${{esc(id)}}" onchange="onRowCheck()"></td>
        <td class="cell-date">${{esc(date)}}</td>
        <td class="cell-cat"><span class="badge badge--blue">${{esc(cat)}}</span></td>
        <td class="cell-content">${{esc(content)}}</td>
        <td class="cell-tags">${{esc(tags)}}</td>
        <td>
          <div class="btn-group">
            <button class="btn-ghost btn-sm" onclick="openEditModal('${{esc(id)}}')">Edit</button>
            <button class="btn-danger btn-sm" onclick="openDeleteModal(['${{esc(id)}}'])">Del</button>
          </div>
        </td>
      </tr>`;
    }}).join('');
  }} catch (e) {{
    body.innerHTML = '<tr><td colspan="6" class="empty-state">Error: ' + esc(e.message) + '</td></tr>';
  }}
}}

function onRowCheck() {{
  selectedIds.clear();
  document.querySelectorAll('.row-check:checked').forEach(cb => selectedIds.add(cb.value));
  updateBatchBar();
}}

function toggleSelectAll() {{
  const checked = document.getElementById('selectAll').checked;
  document.querySelectorAll('.row-check').forEach(cb => {{ cb.checked = checked; }});
  onRowCheck();
}}

function updateBatchBar() {{
  const bar = document.getElementById('batchBar');
  if (selectedIds.size > 0) {{
    bar.classList.remove('hidden');
    document.getElementById('batchCount').textContent = selectedIds.size + ' selected';
  }} else {{
    bar.classList.add('hidden');
  }}
}}

/* -- Edit Modal -- */
async function openEditModal(id) {{
  document.getElementById('editId').value = id;
  document.getElementById('editModalTitle').textContent = 'Edit Memory';
  // Try to load current data
  try {{
    const result = await api('/recall', {{
      method: 'POST',
      body: JSON.stringify({{ query: 'id:' + id, limit: 1 }})
    }});
    const items = Array.isArray(result) ? result : (result.results || []);
    if (items.length) {{
      document.getElementById('editContent').value = items[0].content || '';
      document.getElementById('editTags').value = (Array.isArray(items[0].tags) ? items[0].tags : []).join(', ');
      document.getElementById('editCategory').value = items[0].category || '';
    }}
  }} catch (_) {{}}
  openModal('editModal');
}}

async function saveEdit() {{
  const id = document.getElementById('editId').value;
  const content = document.getElementById('editContent').value.trim();
  const tags = document.getElementById('editTags').value.split(',').map(t => t.trim()).filter(Boolean);
  const category = document.getElementById('editCategory').value.trim();

  const changes = {{}};
  if (content) changes.content = content;
  if (tags.length) changes.tags = tags;
  if (category) changes.category = category;

  try {{
    await api('/memories/' + encodeURIComponent(id), {{
      method: 'PATCH',
      body: JSON.stringify(changes)
    }});
    toast('Memory updated', 'success');
    closeModal('editModal');
    loadManageTable();
  }} catch (e) {{
    toast('Error: ' + e.message, 'error');
  }}
}}

/* -- New Memory Modal -- */
function openNewMemoryModal() {{
  document.getElementById('newContent').value = '';
  document.getElementById('newTags').value = '';
  document.getElementById('newCategory').value = 'general';
  openModal('newModal');
}}

async function saveNew() {{
  const content = document.getElementById('newContent').value.trim();
  if (!content) {{ toast('Content is required', 'error'); return; }}

  const tags = document.getElementById('newTags').value.split(',').map(t => t.trim()).filter(Boolean);
  const category = document.getElementById('newCategory').value.trim() || 'general';

  try {{
    await api('/remember', {{
      method: 'POST',
      body: JSON.stringify({{ content, tags, category }})
    }});
    toast('Memory created', 'success');
    closeModal('newModal');
    loadManageTable();
  }} catch (e) {{
    toast('Error: ' + e.message, 'error');
  }}
}}

/* -- Delete -- */
function openDeleteModal(ids) {{
  deleteQueue = ids;
  document.getElementById('deleteMsg').textContent =
    ids.length === 1 ? 'Delete this memory? This cannot be undone.'
    : 'Delete ' + ids.length + ' memories? This cannot be undone.';
  openModal('deleteModal');
}}

async function confirmDelete() {{
  let ok = 0, fail = 0;
  for (const id of deleteQueue) {{
    try {{
      await api('/memories/' + encodeURIComponent(id), {{ method: 'DELETE' }});
      ok++;
    }} catch (_) {{ fail++; }}
  }}
  toast(ok + ' deleted' + (fail ? ', ' + fail + ' failed' : ''), ok ? 'success' : 'error');
  deleteQueue = [];
  closeModal('deleteModal');
  loadManageTable();
}}

/* -- Batch Actions -- */
async function batchDelete() {{ openDeleteModal([...selectedIds]); }}

async function batchChangeTags() {{
  const newTags = prompt('Enter new tags (comma-separated):');
  if (newTags == null) return;
  const tags = newTags.split(',').map(t => t.trim()).filter(Boolean);
  let ok = 0;
  for (const id of selectedIds) {{
    try {{
      await api('/memories/' + encodeURIComponent(id), {{
        method: 'PATCH',
        body: JSON.stringify({{ tags }})
      }});
      ok++;
    }} catch (_) {{}}
  }}
  toast(ok + ' updated', 'success');
  loadManageTable();
}}

async function batchChangeCategory() {{
  const cat = prompt('Enter new category:');
  if (!cat) return;
  let ok = 0;
  for (const id of selectedIds) {{
    try {{
      await api('/memories/' + encodeURIComponent(id), {{
        method: 'PATCH',
        body: JSON.stringify({{ category: cat }})
      }});
      ok++;
    }} catch (_) {{}}
  }}
  toast(ok + ' updated', 'success');
  loadManageTable();
}}

async function batchMerge() {{
  if (selectedIds.size < 2) {{ toast('Select 2+ memories to merge', 'error'); return; }}
  try {{
    await api('/consolidate', {{
      method: 'POST',
      body: JSON.stringify({{ memory_ids: [...selectedIds] }})
    }});
    toast('Merge complete', 'success');
    loadManageTable();
  }} catch (e) {{
    toast('Error: ' + e.message, 'error');
  }}
}}

async function batchProvenance() {{
  if (selectedIds.size !== 1) {{ toast('Select exactly 1 memory', 'error'); return; }}
  const id = [...selectedIds][0];
  try {{
    const data = await api('/provenance/' + encodeURIComponent(id));
    const pre = JSON.stringify(data, null, 2);
    document.getElementById('editId').value = '';
    document.getElementById('editModalTitle').textContent = 'Provenance';
    document.getElementById('editContent').value = pre;
    document.getElementById('editTags').value = '';
    document.getElementById('editCategory').value = '';
    openModal('editModal');
  }} catch (e) {{
    toast('Error: ' + e.message, 'error');
  }}
}}

/* -- Quick Actions -- */
async function quickAction(path, method, successMsg) {{
  try {{
    await api(path, {{ method }});
    toast(successMsg, 'success');
  }} catch (e) {{
    toast('Error: ' + e.message, 'error');
  }}
}}

/* ========================================
   KNOWLEDGE GRAPH (Cytoscape.js)
   ======================================== */
let cy = null;
let graphData = null;
let graphLoaded = false;

const ENTITY_COLORS = {{
  person: '#6366F1',
  technology: '#22D3EE',
  project: '#F59E0B',
  organization: '#8B5CF6',
  concept: '#DC2626',
  location: '#16A34A',
}};

function entityColor(type) {{
  return ENTITY_COLORS[(type || '').toLowerCase()] || '#94a3b8';
}}

async function loadGraph() {{
  if (window._cytoscapeFailed) {{
    document.getElementById('graphCanvas').innerHTML =
      '<div class="empty-state" style="padding:60px">Cytoscape.js failed to load. Check your network connection.</div>';
    return;
  }}
  // Wait for async CDN load
  if (typeof cytoscape === 'undefined') {{
    if (!window._cytoscapeFailed) {{
      setTimeout(() => loadGraph(), 300);
    }}
    return;
  }}
  if (graphLoaded && cy) return;

  try {{
    const resp = await api('/entity-graph-data?max_nodes=200');
    graphData = resp;
    const statsEl = document.getElementById('graphStats');
    if (statsEl) statsEl.textContent = resp.nodes.length + ' entities, ' + resp.edges.length + ' relations';

    if (!resp.nodes.length) {{
      document.getElementById('graphCanvas').innerHTML =
        '<div class="empty-state" style="padding:60px">No entities yet. Save some memories to build your knowledge graph.</div>';
      return;
    }}

    renderGraph(resp.nodes, resp.edges);
    graphLoaded = true;
  }} catch (e) {{
    document.getElementById('graphCanvas').innerHTML =
      '<div class="empty-state" style="padding:60px">Failed to load graph: ' + esc(e.message) + '</div>';
  }}
}}

function renderGraph(nodes, edges) {{
  const elements = [];

  // Compute max mentions for sizing
  const maxMentions = Math.max(...nodes.map(n => n.mentions || 1), 1);

  nodes.forEach(n => {{
    const size = 20 + Math.min((n.mentions || 1) / maxMentions * 40, 40);
    elements.push({{
      data: {{
        id: 'e' + n.id,
        label: n.name,
        type: n.type || 'unknown',
        mentions: n.mentions || 1,
        first_seen: n.first_seen || '',
        last_seen: n.last_seen || '',
        nodeSize: size,
        color: entityColor(n.type),
      }}
    }});
  }});

  const nodeIds = new Set(nodes.map(n => n.id));
  edges.forEach(e => {{
    if (nodeIds.has(e.source) && nodeIds.has(e.target)) {{
      elements.push({{
        data: {{
          id: 'r' + e.source + '-' + e.target + '-' + (e.predicate || ''),
          source: 'e' + e.source,
          target: 'e' + e.target,
          label: e.predicate || '',
          confidence: e.confidence || 1,
        }}
      }});
    }}
  }});

  cy = cytoscape({{
    container: document.getElementById('graphCanvas'),
    elements: elements,
    style: [
      {{
        selector: 'node',
        style: {{
          'label': 'data(label)',
          'width': 'data(nodeSize)',
          'height': 'data(nodeSize)',
          'background-color': 'data(color)',
          'color': '#e2e8f0',
          'text-valign': 'bottom',
          'text-halign': 'center',
          'font-size': '11px',
          'text-margin-y': 6,
          'text-outline-color': '#09090B',
          'text-outline-width': 2,
          'border-width': 1,
          'border-color': 'data(color)',
          'border-opacity': 0.3,
        }}
      }},
      {{
        selector: 'node:selected',
        style: {{
          'border-width': 3,
          'border-color': '#ffffff',
          'border-opacity': 1,
        }}
      }},
      {{
        selector: 'edge',
        style: {{
          'width': 1.5,
          'line-color': '#27272A',
          'target-arrow-color': '#27272A',
          'target-arrow-shape': 'triangle',
          'arrow-scale': 0.8,
          'curve-style': 'bezier',
          'label': 'data(label)',
          'font-size': '9px',
          'color': '#71717A',
          'text-rotation': 'autorotate',
          'text-outline-color': '#09090B',
          'text-outline-width': 1.5,
        }}
      }},
      {{
        selector: 'edge:selected',
        style: {{
          'line-color': '#6366F1',
          'target-arrow-color': '#6366F1',
          'width': 2.5,
        }}
      }},
      {{
        selector: '.highlighted',
        style: {{
          'border-width': 3,
          'border-color': '#ffffff',
          'border-opacity': 1,
          'z-index': 999,
        }}
      }},
      {{
        selector: '.neighbor',
        style: {{
          'opacity': 1,
        }}
      }},
      {{
        selector: '.dimmed',
        style: {{
          'opacity': 0.15,
        }}
      }},
    ],
    layout: {{
      name: 'cose',
      animate: true,
      animationDuration: 800,
      nodeRepulsion: function() {{ return 8000; }},
      idealEdgeLength: function() {{ return 100; }},
      gravity: 0.25,
      numIter: 300,
      padding: 40,
    }},
    minZoom: 0.2,
    maxZoom: 4,
    wheelSensitivity: 0.3,
  }});

  // Click handler — show detail panel
  cy.on('tap', 'node', function(evt) {{
    const node = evt.target;
    const data = node.data();
    showNodeDetail(node, data);
  }});

  cy.on('tap', function(evt) {{
    if (evt.target === cy) {{
      document.getElementById('graphDetail').style.display = 'none';
      cy.elements().removeClass('highlighted neighbor dimmed');
    }}
  }});
}}

function showNodeDetail(node, data) {{
  document.getElementById('detailName').textContent = data.label;
  document.getElementById('detailType').innerHTML =
    '<span class="badge" style="background:' + esc(data.color) + ';color:#fff;font-size:11px">' + esc(data.type) + '</span>';
  document.getElementById('detailMentions').textContent = data.mentions + ' mention(s)';

  // Get connected edges
  const connectedEdges = node.connectedEdges();
  const relHtml = [];
  connectedEdges.forEach(edge => {{
    const ed = edge.data();
    const src = edge.source().data().label;
    const tgt = edge.target().data().label;
    relHtml.push('<div style="font-size:12px;color:var(--text-muted);padding:4px 0;border-bottom:1px solid var(--border)">'
      + esc(src) + ' <span style="color:var(--blue)">' + esc(ed.label || '?') + '</span> ' + esc(tgt) + '</div>');
  }});

  document.getElementById('detailRelations').innerHTML =
    relHtml.length ? '<div style="margin-top:8px"><div style="font-size:12px;font-weight:600;margin-bottom:4px">Relations (' + relHtml.length + ')</div>' + relHtml.join('') + '</div>'
    : '<div style="color:var(--text-dim);font-size:12px;margin-top:8px">No direct relations</div>';

  document.getElementById('graphDetail').style.display = 'block';

  // Highlight neighbors
  cy.elements().removeClass('highlighted neighbor dimmed');
  cy.elements().addClass('dimmed');
  node.removeClass('dimmed').addClass('highlighted');
  node.neighborhood().removeClass('dimmed').addClass('neighbor');
}}

function filterGraph() {{
  if (!cy || !graphData) return;
  const search = (document.getElementById('graphSearch').value || '').toLowerCase();
  const typeFilter = document.getElementById('graphTypeFilter').value;

  cy.nodes().forEach(node => {{
    const data = node.data();
    const nameMatch = !search || data.label.toLowerCase().includes(search);
    const typeMatch = !typeFilter || (data.type || '').toLowerCase() === typeFilter;
    if (nameMatch && typeMatch) {{
      node.style('display', 'element');
    }} else {{
      node.style('display', 'none');
    }}
  }});

  cy.edges().forEach(edge => {{
    const src = edge.source();
    const tgt = edge.target();
    if (src.style('display') === 'none' || tgt.style('display') === 'none') {{
      edge.style('display', 'none');
    }} else {{
      edge.style('display', 'element');
    }}
  }});
}}

function resetGraphView() {{
  if (!cy) return;
  document.getElementById('graphSearch').value = '';
  document.getElementById('graphTypeFilter').value = '';
  document.getElementById('graphDetail').style.display = 'none';
  cy.elements().removeClass('highlighted neighbor dimmed');
  cy.nodes().forEach(n => n.style('display', 'element'));
  cy.edges().forEach(e => e.style('display', 'element'));
  cy.fit(undefined, 40);
}}

/* ========================================
   INIT
   ======================================== */

document.addEventListener('DOMContentLoaded', () => {{
  // Load filter options
  loadTagOptions();
  loadCategoryOptions();

  // Route
  navigate(location.hash || '#overview');

  // Async CDN init — retry until loaded or failed
  function initChartJs() {{
    if (typeof Chart !== 'undefined') {{
      chartjsReady = true;
      (async () => {{
        try {{
          const data = await api('/knowledge-stats');
          updateGrowthChart(data);
        }} catch (_) {{}}
      }})();
    }} else if (!window._chartjsFailed) {{
      setTimeout(initChartJs, 200);
    }} else {{
      showGrowthFallback(INITIAL);
    }}
  }}
  initChartJs();

  function initMermaid() {{
    if (typeof mermaid !== 'undefined') {{
      try {{ mermaid.initialize({{ startOnLoad: false, theme: 'dark' }}); }} catch(_) {{}}
      const mermaidEl = document.getElementById('mermaidGraph');
      if (mermaidEl && mermaidEl.textContent.trim()) {{
        try {{
          mermaid.run({{ nodes: [mermaidEl] }});
        }} catch(_) {{
          try {{ mermaid.init(undefined, mermaidEl); }} catch(__) {{}}
        }}
      }}
    }} else if (!window._mermaidFailed) {{
      setTimeout(initMermaid, 200);
    }}
  }}
  initMermaid();
}});
</script>
</body>
</html>"""
