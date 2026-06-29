"""Lightweight logging configuration.

A single :func:`get_logger` gives every module a console + rotating-ish file
logger writing to ``data/logs/qrh.log``. Agent *decisions* are additionally
persisted to the ``agent_events`` table (see ``storage.repository``); this is
just the human-readable text log.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from .config import get_config

_CONFIGURED = False
_FMT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def _configure_root() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    cfg = get_config()
    cfg.logs_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("qrh")
    root.setLevel(logging.INFO)
    root.propagate = False

    formatter = logging.Formatter(_FMT)

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    root.addHandler(console)

    try:
        fileh = RotatingFileHandler(
            cfg.logs_dir / "qrh.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
        fileh.setFormatter(formatter)
        root.addHandler(fileh)
    except Exception:  # pragma: no cover - never fail because logging can't open a file
        pass

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger under the ``qrh`` root."""
    _configure_root()
    return logging.getLogger(f"qrh.{name}")
