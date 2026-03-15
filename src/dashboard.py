"""Web dashboard for Tessera — single-page HTML served from FastAPI."""

from __future__ import annotations

import html
import logging

logger = logging.getLogger(__name__)


def _card(title: str, value: str, subtitle: str = "", color: str = "#3b82f6") -> str:
    return f"""
    <div style="background:#1e293b;border-radius:12px;padding:24px;min-width:180px;border-left:4px solid {color}">
      <div style="color:#94a3b8;font-size:13px;margin-bottom:8px">{html.escape(title)}</div>
      <div style="color:#f1f5f9;font-size:28px;font-weight:700">{html.escape(str(value))}</div>
      {f'<div style="color:#64748b;font-size:12px;margin-top:4px">{html.escape(subtitle)}</div>' if subtitle else ''}
    </div>"""


def render_dashboard(stats: dict) -> str:
    """Render the dashboard HTML page.

    Args:
        stats: Dict with keys: memory_count, entity_count, relationship_count,
               health_score, contradictions, consolidation_clusters,
               recent_memories, entity_graph_mermaid.
    """
    memory_count = stats.get("memory_count", 0)
    entity_count = stats.get("entity_count", 0)
    rel_count = stats.get("relationship_count", 0)
    health_score = stats.get("health_score", "—")
    contradiction_count = stats.get("contradiction_count", 0)
    cluster_count = stats.get("cluster_count", 0)
    recent = stats.get("recent_memories", [])
    mermaid = stats.get("entity_graph_mermaid", "")
    version = stats.get("version", "dev")

    # Cards
    cards = "".join([
        _card("Memories", str(memory_count), "active memories", "#3b82f6"),
        _card("Entities", str(entity_count), f"{rel_count} relationships", "#10b981"),
        _card("Health", str(health_score), "overall score", "#f59e0b" if health_score != "—" else "#64748b"),
        _card("Contradictions", str(contradiction_count), "detected", "#ef4444" if contradiction_count else "#10b981"),
        _card("Consolidation", str(cluster_count), "similar clusters", "#8b5cf6" if cluster_count else "#10b981"),
    ])

    # Recent memories table
    mem_rows = ""
    for m in recent[:10]:
        date = html.escape(str(m.get("date", ""))[:10])
        cat = html.escape(str(m.get("category", "")))
        tags = html.escape(str(m.get("tags", "")))
        content = html.escape(str(m.get("content", ""))[:120])
        mem_rows += f"""
        <tr style="border-bottom:1px solid #334155">
          <td style="padding:10px;color:#94a3b8;white-space:nowrap">{date}</td>
          <td style="padding:10px"><span style="background:#1e3a5f;color:#60a5fa;padding:2px 8px;border-radius:4px;font-size:12px">{cat}</span></td>
          <td style="padding:10px;color:#e2e8f0">{content}</td>
          <td style="padding:10px;color:#64748b;font-size:12px">{tags}</td>
        </tr>"""

    mem_table = f"""
    <div style="background:#1e293b;border-radius:12px;padding:24px;margin-top:24px">
      <h2 style="color:#f1f5f9;font-size:18px;margin:0 0 16px">Recent Memories</h2>
      <div style="overflow-x:auto">
        <table style="width:100%;border-collapse:collapse">
          <thead>
            <tr style="border-bottom:2px solid #334155">
              <th style="text-align:left;padding:10px;color:#94a3b8;font-size:13px">Date</th>
              <th style="text-align:left;padding:10px;color:#94a3b8;font-size:13px">Category</th>
              <th style="text-align:left;padding:10px;color:#94a3b8;font-size:13px">Content</th>
              <th style="text-align:left;padding:10px;color:#94a3b8;font-size:13px">Tags</th>
            </tr>
          </thead>
          <tbody>{mem_rows}</tbody>
        </table>
      </div>
      {f'<div style="color:#64748b;margin-top:12px;font-size:13px">Showing {len(recent[:10])} of {memory_count} memories</div>' if memory_count else ''}
    </div>""" if recent else ""

    # Entity graph (Mermaid)
    graph_section = ""
    if mermaid:
        graph_section = f"""
    <div style="background:#1e293b;border-radius:12px;padding:24px;margin-top:24px">
      <h2 style="color:#f1f5f9;font-size:18px;margin:0 0 16px">Entity Knowledge Graph</h2>
      <div class="mermaid" style="background:#0f172a;border-radius:8px;padding:16px;overflow-x:auto">
{html.escape(mermaid)}
      </div>
    </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Tessera Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
  <script>mermaid.initialize({{startOnLoad:true,theme:'dark'}});</script>
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ background:#0f172a; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; color:#e2e8f0; min-height:100vh; }}
    a {{ color:#60a5fa; text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
  </style>
</head>
<body>
  <div style="max-width:1200px;margin:0 auto;padding:24px">
    <header style="display:flex;justify-content:space-between;align-items:center;margin-bottom:32px">
      <div>
        <h1 style="font-size:24px;font-weight:700;color:#f1f5f9">
          <span style="color:#3b82f6">&#9670;</span> Tessera
        </h1>
        <div style="color:#64748b;font-size:13px;margin-top:4px">Personal Knowledge Layer &mdash; v{html.escape(version)}</div>
      </div>
      <div style="display:flex;gap:12px;font-size:13px">
        <a href="/docs">API Docs</a>
        <a href="/health">Health</a>
        <span style="color:#334155">|</span>
        <span style="color:#64748b">Auto-refreshes every 30s</span>
      </div>
    </header>

    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px">
      {cards}
    </div>

    {graph_section}
    {mem_table}

    <footer style="text-align:center;color:#475569;font-size:12px;margin-top:40px;padding:20px">
      Tessera v{html.escape(version)} &mdash; <a href="https://github.com/besslframework-stack/project-tessera">GitHub</a>
    </footer>
  </div>

  <script>setTimeout(()=>location.reload(), 30000);</script>
</body>
</html>"""
