"""Shared pytest fixtures.

Every test runs against an isolated temp DB + data/experiments dirs (so the dev
DB is never touched), with the arXiv interval set to 0 and the budget profile set
to ``medium``. The network is always mocked via an injected fetcher.
"""

from __future__ import annotations

import pathlib
import shutil
import sys
from datetime import date

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# A static, fixed-date Atom feed for deterministic parsing tests.
STATIC_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2606.01234v2</id>
    <title>Adaptive QPEPS-QMERA ansatz for the transverse-field Ising model</title>
    <summary>We propose a novel hybrid tensor network ansatz combining PEPS and MERA layers
    for VQE. We show adaptive depth reduces energy error at fixed parameter count on a small
    Ising model benchmark, outperforming a fixed-depth MPS baseline.</summary>
    <published>2026-06-05T10:00:00Z</published>
    <updated>2026-06-06T10:00:00Z</updated>
    <author><name>A. Researcher</name></author>
    <author><name>B. Scientist</name></author>
    <link href="http://arxiv.org/pdf/2606.01234v2" rel="related" type="application/pdf"/>
    <category term="quant-ph"/>
    <category term="cond-mat.str-el"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2606.05678v1</id>
    <title>Circuit cutting for distributed simulation of Heisenberg chains</title>
    <summary>We introduce a circuit knitting scheme for distributed quantum computing and
    demonstrate reduced sampling overhead on a Heisenberg model benchmark.</summary>
    <published>2026-06-05T11:00:00Z</published>
    <updated>2026-06-05T11:00:00Z</updated>
    <author><name>C. Cutter</name></author>
    <link href="http://arxiv.org/pdf/2606.05678v1" rel="related" type="application/pdf"/>
    <category term="quant-ph"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2606.09999v1</id>
    <title>A review of classical sorting networks</title>
    <summary>This survey reviews classical sorting algorithms with no quantum content.</summary>
    <published>2026-06-05T12:00:00Z</published>
    <updated>2026-06-05T12:00:00Z</updated>
    <author><name>S. Sorter</name></author>
    <link href="http://arxiv.org/pdf/2606.09999v1" rel="related" type="application/pdf"/>
    <category term="cs.DS"/>
  </entry>
</feed>"""


def make_today_feed() -> bytes:
    """Same papers but published today, so the daily-run date window includes them."""
    today = date.today().isoformat()
    return STATIC_FEED.replace(b"2026-06-05T", today.encode() + b"T").replace(
        b"2026-06-06T", today.encode() + b"T"
    )


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Point all paths at a temp dir, reset config cache, init DB, copy templates."""
    monkeypatch.setenv("QRH_DB_PATH", str(tmp_path / "dev.sqlite3"))
    monkeypatch.setenv("QRH_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("QRH_EXPERIMENTS_DIR", str(tmp_path / "experiments"))
    monkeypatch.setenv("QRH_ARXIV_MIN_INTERVAL", "0")
    monkeypatch.setenv("QRH_BUDGET_PROFILE", "medium")
    monkeypatch.setenv("QRH_EXPERIMENT_TIMEOUT_SECONDS", "60")
    monkeypatch.delenv("QRH_APPROVAL_GRANTED", raising=False)

    from researcher_mcp.config import get_config, reset_config_cache

    reset_config_cache()
    cfg = get_config()
    cfg.ensure_dirs()

    src_templates = ROOT / "experiments" / "templates"
    if src_templates.exists():
        shutil.copytree(src_templates, cfg.experiments_dir / "templates", dirs_exist_ok=True)

    from researcher_mcp.storage.db import init_db

    init_db(cfg)
    yield cfg
    reset_config_cache()


@pytest.fixture
def mock_client():
    """An ArxivClient that returns the static fixture feed (no network)."""
    from researcher_mcp.ingest.arxiv_client import ArxivClient

    return ArxivClient(min_interval=0.0, fetcher=lambda _url: STATIC_FEED)


@pytest.fixture
def today_client():
    """An ArxivClient whose papers are published today (for daily-run tests)."""
    from researcher_mcp.ingest.arxiv_client import ArxivClient

    feed = make_today_feed()
    return ArxivClient(min_interval=0.0, fetcher=lambda _url: feed)
