"""Seed the Quantum Research Hub with realistic demo data — no network.

Drives the *real* orchestrator pipeline against a curated offline arXiv feed so
the dashboard immediately shows papers, cards, ideas, an experiment (built, run,
validated), agent activity, budget usage, and a daily report.

Usage::

    python scripts/seed_demo.py            # reset + seed
    python scripts/seed_demo.py --keep     # seed without resetting the DB
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from datetime import date

# --- bootstrap sys.path -------------------------------------------------------
_here = pathlib.Path(__file__).resolve()
_root = next((p for p in _here.parents if (p / "pyproject.toml").exists()), _here.parents[-1])
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
# ------------------------------------------------------------------------------

from researcher_mcp.ingest.arxiv_client import ArxivClient  # noqa: E402
from researcher_mcp.storage.db import init_db, reset_db  # noqa: E402

# Curated demo papers spanning the user's research focus areas.
_DEMO = [
    ("2606.10001",
     "Hybrid QPEPS-QMERA ansatz with adaptive bond dimension for 2D lattices",
     "We propose a novel hybrid tensor network ansatz that combines short-range PEPS "
     "layers with adaptive MERA layers for variational quantum eigensolver (VQE) "
     "simulations of 2D lattice models. We show that adaptive bond dimension reduces "
     "energy error at fixed parameter count on a transverse-field Ising model benchmark, "
     "outperforming a fixed-depth MPS baseline.",
     ["quant-ph", "cond-mat.str-el"]),
    ("2606.10002",
     "Adaptive-ansatz VQE for molecular Hamiltonians with measurement reduction",
     "We present a variational quantum eigensolver with adaptive ansatz growth for "
     "molecular Hamiltonians such as H2 and LiH. We demonstrate that operator pools "
     "reduce parameter count while preserving accuracy, and we introduce a measurement "
     "reduction scheme based on classical shadows.",
     ["quant-ph"]),
    ("2606.10003",
     "Circuit cutting and knitting for distributed simulation of Heisenberg chains",
     "We introduce a circuit knitting scheme for distributed quantum computing that cuts "
     "entangling gates to simulate Heisenberg spin chains across small devices. We show "
     "reduced sampling overhead versus naive entanglement forging on a lattice benchmark.",
     ["quant-ph", "cs.ET"]),
    ("2606.10004",
     "Barren plateau mitigation via local cost functions in quantum machine learning",
     "We study barren plateaus in quantum machine learning and quantum feature maps. We "
     "propose local cost functions and data re-uploading strategies and demonstrate "
     "improved trainability of quantum neural networks on a small synthetic dataset.",
     ["quant-ph", "cs.LG"]),
    ("2606.10005",
     "Classical shadows for efficient error mitigation in variational algorithms",
     "We apply classical shadow tomography to error mitigation and measurement reduction "
     "in variational quantum algorithms. We find that shadow estimation lowers the shot "
     "budget for energy estimation in VQE on an Ising model.",
     ["quant-ph", "physics.comp-ph"]),
]


def _build_feed() -> bytes:
    today = date.today().isoformat()
    entries = []
    for aid, title, summary, cats in _DEMO:
        cat_xml = "".join(f'<category term="{c}"/>' for c in cats)
        entries.append(f"""  <entry>
    <id>http://arxiv.org/abs/{aid}v1</id>
    <title>{title}</title>
    <summary>{summary}</summary>
    <published>{today}T09:00:00Z</published>
    <updated>{today}T09:00:00Z</updated>
    <author><name>Demo Author</name></author>
    <link href="http://arxiv.org/pdf/{aid}v1" rel="related" type="application/pdf"/>
    {cat_xml}
  </entry>""")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<feed xmlns="http://www.w3.org/2005/Atom">\n'
        + "\n".join(entries)
        + "\n</feed>"
    ).encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed demo data into the Quantum Research Hub.")
    parser.add_argument("--keep", action="store_true", help="do not reset the DB before seeding")
    parser.add_argument("--profile", default="medium", choices=["low", "medium", "high"])
    args = parser.parse_args(argv)

    if args.keep:
        init_db()
    else:
        reset_db(confirm=True)
        print("Reset DB.")

    feed = _build_feed()
    client = ArxivClient(min_interval=0.0, fetcher=lambda _url: feed)

    from orchestrator.daily_run import _print_summary, run_daily

    summary = run_daily(args.profile, arxiv_client=client, lookback_days=7)
    _print_summary(summary)
    print(f"Seeded {len(_DEMO)} demo papers. Open the dashboard:\n"
          f"  streamlit run apps/dashboard/Home.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
