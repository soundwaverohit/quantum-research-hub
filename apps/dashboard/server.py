"""Zero-dependency HTTP dashboard for the Quantum Research Hub.

A pure-stdlib (``http.server``) dashboard that reads SQLite + artifact files and
renders the same views as the Streamlit app: Overview, Papers, Ideas,
Experiments, Agent Logs, Budget, Reports. It needs NO third-party packages, so
it runs anywhere the core system runs — including environments where the
Streamlit/pyarrow stack is unhappy.

Run from the repo root::

    python -m apps.dashboard.server                 # http://127.0.0.1:8533
    python apps/dashboard/server.py --port 8600

The MCP server need not be running; this dashboard is read-only.
"""

from __future__ import annotations

# --- bootstrap sys.path -------------------------------------------------------
import pathlib
import sys

_here = pathlib.Path(__file__).resolve()
_root = next((p for p in _here.parents if (p / "pyproject.toml").exists()), _here.parents[-1])
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
# ------------------------------------------------------------------------------

import argparse
import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from researcher_mcp.config import get_config
from researcher_mcp.storage import repository as repo
from researcher_mcp.tools import budget_tools, experiment_tools, paper_tools

NAV = [
    ("/", "Overview"), ("/papers", "Papers"), ("/ideas", "Ideas"),
    ("/experiments", "Experiments"), ("/agents", "Agent Logs"),
    ("/budget", "Budget"), ("/reports", "Reports"),
]

CSS = """
:root{--bg:#0f1117;--card:#1a1d26;--ink:#e6e8ee;--muted:#9aa3b2;--accent:#7c5cff;--ok:#36c08a;--warn:#e0566b;--line:#2a2e3a}
*{box-sizing:border-box}body{margin:0;font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--ink)}
header{background:linear-gradient(90deg,#13151d,#1a1d26);border-bottom:1px solid var(--line);padding:14px 22px}
header h1{margin:0;font-size:18px}header .sub{color:var(--muted);font-size:12px}
nav{display:flex;gap:4px;flex-wrap:wrap;padding:10px 22px;background:#13151d;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:5}
nav a{color:var(--muted);text-decoration:none;padding:6px 12px;border-radius:8px}
nav a:hover,nav a.active{background:var(--accent);color:#fff}
main{padding:22px;max-width:1200px;margin:0 auto}
h2{font-size:16px;margin:22px 0 10px;border-left:3px solid var(--accent);padding-left:8px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:8px 0 4px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}
.card .n{font-size:26px;font-weight:700}.card .l{color:var(--muted);font-size:12px}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;margin:6px 0}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:top}
th{background:#20242f;color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.04em}
tr:last-child td{border-bottom:none}
a{color:#9b86ff}.pill{padding:2px 8px;border-radius:99px;font-size:12px;background:#262b38}
.pill.extend,.pill.accepted,.pill.validated{background:rgba(54,192,138,.18);color:var(--ok)}
.pill.ignore,.pill.rejected,.pill.failed{background:rgba(224,86,107,.18);color:var(--warn)}
.pill.reproduce,.pill.summarize{background:rgba(124,92,255,.2);color:#b9a7ff}
pre{background:#0c0e14;border:1px solid var(--line);border-radius:10px;padding:14px;overflow:auto;white-space:pre-wrap}
.muted{color:var(--muted)}.right{text-align:right}.mono{font-family:ui-monospace,Menlo,monospace}
.idealist{display:flex;flex-direction:column;gap:10px;margin-top:12px}
details.idea{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}
details.idea>summary{list-style:none;cursor:pointer;padding:13px 16px;display:flex;justify-content:space-between;align-items:center;gap:14px}
details.idea>summary::-webkit-details-marker{display:none}
details.idea[open]>summary{border-bottom:1px solid var(--line)}
details.idea:hover{border-color:var(--accent)}
.idea-left{display:flex;align-items:center;gap:9px;min-width:0}
.caret{color:var(--accent);display:inline-block;transition:transform .15s;flex:none}
details.idea[open] .caret{transform:rotate(90deg)}
.idea-title{font-weight:600;font-size:15px}
.idea-meta{display:flex;gap:6px;flex-wrap:wrap;align-items:center;white-space:nowrap}
.idea-body{padding:4px 16px 16px 40px}
.field{margin:13px 0}
.flabel{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px}
.fval{font-size:14px}.fval ul{margin:4px 0;padding-left:20px}
"""


def esc(v) -> str:
    return html.escape("" if v is None else str(v))


def pill(text) -> str:
    t = esc(text)
    cls = t.lower().replace(" ", "")
    return f'<span class="pill {cls}">{t}</span>'


def page(active: str, title: str, body: str) -> bytes:
    nav = "".join(
        f'<a href="{href}" class="{"active" if href == active else ""}">{esc(label)}</a>'
        for href, label in NAV
    )
    doc = f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · Quantum Research Hub</title><style>{CSS}</style></head><body>
<header><h1>⚛️ Quantum Research Hub</h1>
<div class="sub">Local-first, MCP-powered autonomous quantum-computing research — read-only dashboard</div></header>
<nav>{nav}</nav><main>{body}</main></body></html>"""
    return doc.encode("utf-8")


def table(headers: list[str], rows: list[list[str]], empty: str = "Nothing here yet.") -> str:
    if not rows:
        return f'<p class="muted">{esc(empty)}</p>'
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _action(o) -> str:
    return str(getattr(o.recommended_action, "value", o.recommended_action))


def _status(o) -> str:
    return str(getattr(o.status, "value", o.status))


# --- views --------------------------------------------------------------------
def view_overview() -> str:
    c = repo.overview_counts()
    b = budget_tools.get_budget_status()
    cards = [
        ("Papers", c["papers_total"]), ("Today", c["papers_today"]),
        ("High-relevance", c["papers_high_relevance"]), ("Ideas", c["ideas_total"]),
        ("Experiments", c["experiments_total"]), ("Validated", c["experiments_validated"]),
        ("Runs", c["runs_total"]), ("Agent actions", c["agent_events_total"]),
    ]
    cards_html = "".join(f'<div class="card"><div class="n">{v}</div><div class="l">{esc(l)}</div></div>' for l, v in cards)

    papers = repo.list_papers(limit=8, order_by="created_at DESC")
    prows = [[f'<a href="/papers?id={esc(p.arxiv_id)}">{esc(p.title[:80])}</a>',
              esc(p.relevance_score), pill(_action(p))] for p in papers]
    events = repo.list_agent_events(limit=10)
    erows = [[esc(e.timestamp), esc(e.agent_name), esc(e.action), esc(e.output_summary[:90]), pill(e.status)] for e in events]

    return (
        f'<h2>Today &amp; totals</h2><div class="cards">{cards_html}</div>'
        f'<p class="muted">Budget profile: <b>{esc(b["profile"])}</b></p>'
        f"<h2>Recent papers</h2>{table(['Title', 'Relevance', 'Action'], prows, 'No papers — run the daily loop.')}"
        f"<h2>Recent agent activity</h2>{table(['Time', 'Agent', 'Action', 'Output', 'Status'], erows)}"
    )


def view_papers(qs: dict) -> str:
    if qs.get("id"):
        return _paper_detail(qs["id"][0])
    papers = repo.list_papers(limit=500)
    rows = [[
        esc(p.published_date), f'<a href="/papers?id={esc(p.arxiv_id)}">{esc(p.title[:90])}</a>',
        f'<span class="mono">{esc(p.arxiv_id)}</span>', esc(", ".join(p.categories[:2])),
        esc(p.relevance_score), esc(p.novelty_score), pill(_action(p)), esc(_status(p)),
    ] for p in papers]
    return (f"<h2>Papers ({len(papers)})</h2>"
            + table(["Date", "Title", "arXiv", "Category", "Rel", "Nov", "Action", "Status"], rows,
                    "No papers yet — run `python -m orchestrator.daily_run --profile low`."))


def _paper_detail(arxiv_id: str) -> str:
    card = paper_tools.get_paper_card(arxiv_id)
    if "error" in card:
        return f'<h2>Paper</h2><p class="muted">{esc(card["error"])}</p>'
    def ul(items):
        return "<ul>" + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>" if items else '<p class="muted">(none)</p>'
    return (
        f'<p><a href="/papers">← all papers</a></p>'
        f'<h2>{esc(card["title"])}</h2>'
        f'<p class="muted mono">{esc(card["arxiv_id"])} · {esc(card.get("published"))} · '
        f'{esc(", ".join(card.get("categories", [])))}</p>'
        f'<div class="cards"><div class="card"><div class="n">{esc(card["relevance_score"])}</div><div class="l">Relevance</div></div>'
        f'<div class="card"><div class="n">{esc(card["novelty_score"])}</div><div class="l">Novelty</div></div>'
        f'<div class="card"><div class="n">{esc(card["implementation_difficulty"])}</div><div class="l">Difficulty</div></div>'
        f'<div class="card"><div class="n">{pill(card["recommended_action"])}</div><div class="l">Action</div></div></div>'
        f'<h2>Core contribution</h2><p>{esc(card.get("core_contribution"))}</p>'
        f'<h2>Methods</h2>{ul(card.get("methods", []))}'
        f'<h2>Key claims</h2>{ul(card.get("claims", []))}'
        f'<h2>Datasets / benchmarks</h2>{ul(card.get("datasets_or_benchmarks", []))}'
        f'<h2>Relevance to your research</h2><p>{esc(card.get("relevance_to_user"))}</p>'
        f'<h2>Possible experiments</h2>{ul(card.get("possible_experiments", []))}'
        f'<h2>Abstract</h2><p class="muted">{esc(card.get("abstract"))}</p>'
    )


def _idea_card(i) -> str:
    def field(label: str, val: str) -> str:
        if not val:
            return ""
        return (f'<div class="field"><div class="flabel">{esc(label)}</div>'
                f'<div class="fval">{esc(val)}</div></div>')

    fm = i.failure_modes or []
    fm_html = ("<ul>" + "".join(f"<li>{esc(x)}</li>" for x in fm) + "</ul>"
               if fm else '<span class="muted">(none listed)</span>')
    sources = " · ".join(
        f'<a href="/papers?id={esc(s)}">{esc(s)}</a>' for s in i.source_arxiv_ids
    ) or '<span class="muted">(none)</span>'

    summary = (
        f'<span class="idea-left"><span class="caret">▸</span>'
        f'<span class="idea-title">{esc(i.title)}</span></span>'
        f'<span class="idea-meta"><span class="pill">nov {esc(i.novelty_score)}</span>'
        f'<span class="pill">feas {esc(i.feasibility_score)}</span>'
        f'{pill(_status(i))}</span>'
    )
    body = (
        f'<p class="muted mono">{esc(i.id)}</p>'
        + field("Hypothesis", i.hypothesis)
        + field("Observation", i.observation)
        + field("Smallest experiment", i.smallest_experiment)
        + field("Baseline", i.baseline)
        + field("Metric", i.metric)
        + field("Expected runtime", i.expected_runtime)
        + f'<div class="field"><div class="flabel">Failure modes</div><div class="fval">{fm_html}</div></div>'
        + f'<div class="field"><div class="flabel">Source papers</div><div class="fval">{sources}</div></div>'
    )
    return (f'<details class="idea"><summary>{summary}</summary>'
            f'<div class="idea-body">{body}</div></details>')


def view_ideas(qs: dict) -> str:
    ideas = repo.list_ideas(limit=500)
    if not ideas:
        return ('<h2>Research ideas (0)</h2>'
                '<p class="muted">No ideas yet — run the daily loop.</p>')
    cards = "".join(_idea_card(i) for i in ideas)
    return (f"<h2>Research ideas ({len(ideas)})</h2>"
            f'<p class="muted">Click any idea to expand its full hypothesis, smallest experiment, '
            f'baseline, metric, and failure modes. Every idea cites at least one source paper.</p>'
            f'<div class="idealist">{cards}</div>')


def view_experiments(qs: dict) -> str:
    if qs.get("id"):
        return _experiment_detail(qs["id"][0])
    data = experiment_tools.list_experiments(limit=500)["experiments"]
    rows = [[
        f'<a href="/experiments?id={esc(e["id"])}"><span class="mono">{esc(e["id"])}</span></a>',
        esc(e["title"][:60]), pill(e["status"]), esc(e["baseline"]),
        esc(e["metric"]), esc(e["best_result"]), pill(e["validator_verdict"]),
    ] for e in data]
    return (f"<h2>Experiments ({len(data)})</h2>"
            + table(["ID", "Title", "Status", "Baseline", "Metric", "Best (err)", "Verdict"], rows,
                    "No experiments — run `--profile medium` or seed demo data."))


def _experiment_detail(exp_id: str) -> str:
    d = experiment_tools.get_experiment(exp_id)
    if "error" in d:
        return f'<h2>Experiment</h2><p class="muted">{esc(d["error"])}</p>'
    exp, metrics = d["experiment"], d.get("metrics") or {}
    mrows = [[esc(k), esc(v)] for k, v in metrics.items()]
    return (
        f'<p><a href="/experiments">← all experiments</a></p>'
        f'<h2>{esc(exp["title"])}</h2>'
        f'<p class="muted mono">{esc(exp["id"])} · status {pill(exp["status"])}</p>'
        f"<h2>Metrics</h2>{table(['Metric', 'Value'], mrows, 'Not run yet.')}"
        f'<h2>Validator notes</h2><pre>{esc(d.get("validator_notes") or "(pending)")}</pre>'
        f'<h2>Config</h2><pre>{esc(json.dumps(d.get("config") or {}, indent=2))}</pre>'
        f'<h2>Files</h2><pre>{esc(chr(10).join(d.get("files") or []))}</pre>'
    )


def view_agents(qs: dict) -> str:
    events = repo.list_agent_events(limit=500)
    rows = [[esc(e.timestamp), esc(e.agent_name), esc(e.action), esc(e.input_summary[:60]),
             esc(e.output_summary[:90]), pill(e.status),
             f'<span class="mono">{esc((e.artifact_path or "")[-40:])}</span>'] for e in events]
    return (f"<h2>Agent activity ({len(events)})</h2>"
            f'<p class="muted">Every agent and MCP tool action is logged — the audit trail.</p>'
            + table(["Time", "Agent", "Action", "Input", "Output", "Status", "Artifact"], rows))


def view_budget(qs: dict) -> str:
    profile = qs.get("profile", [None])[0]
    s = budget_tools.get_budget_status(profile)
    rows = [[esc(k), esc(s["used"].get(k, 0)), esc(s["caps"][k]), esc(s["remaining"][k])] for k in s["caps"]]
    events = repo.list_budget_events(limit=200)
    erows = [[esc(e.timestamp), esc(e.budget_profile), esc(e.event_type),
              esc(e.local_runtime_seconds), esc(e.notes)] for e in events]
    links = " · ".join(f'<a href="/budget?profile={p}">{p}</a>' for p in ("low", "medium", "high"))
    return (f"<h2>Budget — profile {esc(s['profile'])}</h2><p class='muted'>switch: {links}</p>"
            + table(["Resource", "Used", "Cap", "Remaining"], rows)
            + f"<h2>Budget event log</h2>{table(['Time', 'Profile', 'Event', 'Runtime(s)', 'Notes'], erows)}")


def view_reports(qs: dict) -> str:
    cfg = get_config()
    kind = qs.get("kind", ["daily"])[0]
    if kind not in {"daily", "weekly"}:
        kind = "daily"
    report_dir = cfg.reports_dir / "weekly" if kind == "weekly" else cfg.daily_reports_dir
    files = sorted(report_dir.glob("*.md"), reverse=True) if report_dir.exists() else []
    switch = ' · '.join(f'<a href="/reports?kind={k}">{k}</a>' for k in ("daily", "weekly"))
    if qs.get("name"):
        name = qs["name"][0]
        match = next((f for f in files if f.name == name), None)
        if match:
            return (f'<p><a href="/reports?kind={esc(kind)}">← all reports</a></p>'
                    f'<pre>{esc(match.read_text(encoding="utf-8"))}</pre>')
    rows = [[f'<a href="/reports?kind={esc(kind)}&name={esc(f.name)}">{esc(f.stem)}</a>'] for f in files]
    return (
        f"<h2>{esc(kind.title())} reports ({len(files)})</h2>"
        f"<p class='muted'>switch: {switch}</p>"
        + table(["Report"], rows, "No reports yet.")
    )


ROUTES = {
    "/": ("Overview", lambda qs: view_overview()),
    "/papers": ("Papers", view_papers),
    "/ideas": ("Ideas", view_ideas),
    "/experiments": ("Experiments", view_experiments),
    "/agents": ("Agent Logs", view_agents),
    "/budget": ("Budget", view_budget),
    "/reports": ("Reports", view_reports),
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):  # quiet
        pass

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path == "/health":
            self._send(b"ok", "text/plain")
            return
        route = ROUTES.get(path)
        if route is None:
            self._send(page(path, "Not found", '<h2>404</h2><p class="muted">No such page.</p>'), code=404)
            return
        title, fn = route
        try:
            body = fn(parse_qs(parsed.query))
        except Exception as exc:  # noqa: BLE001 - never crash the dashboard
            body = f'<h2>Error</h2><pre>{esc(repr(exc))}</pre>'
        self._send(page(path, title, body))

    def _send(self, body: bytes, content_type: str = "text/html; charset=utf-8", code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8533)
    args = parser.parse_args(argv)

    get_config().ensure_dirs()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}"
    print(f"Quantum Research Hub dashboard → {url}  (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
