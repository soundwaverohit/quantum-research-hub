"""Optional PDF text extraction (guarded ``pypdf`` adapter).

``pypdf`` is an optional dependency (``pip install '.[pdf]'``). When it is not
installed, :func:`pdf_available` returns ``False`` and :func:`parse_pdf`
returns a structured "unavailable" result instead of raising. This keeps the
MVP runnable with zero extra installs while leaving a clean seam for full-text
ingestion later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..logging_utils import get_logger

log = get_logger("ingest.pdf_parser")


def pdf_available() -> bool:
    try:
        import pypdf  # noqa: F401

        return True
    except Exception:
        return False


@dataclass
class ParsedPdf:
    ok: bool
    text: str = ""
    num_pages: int = 0
    reason: str = ""
    sections: dict[str, str] = field(default_factory=dict)


def parse_pdf(pdf_path: Path, *, max_pages: int = 40) -> ParsedPdf:
    """Extract plain text from a local PDF. Best-effort, capped at ``max_pages``."""
    if not pdf_available():
        return ParsedPdf(
            ok=False,
            reason="pypdf not installed; install optional extra '.[pdf]' to enable "
            "full-text parsing. The MVP works from metadata + abstract without it.",
        )
    if not pdf_path.exists():
        return ParsedPdf(ok=False, reason=f"file not found: {pdf_path}")

    try:
        import pypdf

        reader = pypdf.PdfReader(str(pdf_path))
        pages = reader.pages[:max_pages]
        texts = []
        for page in pages:
            try:
                texts.append(page.extract_text() or "")
            except Exception:  # noqa: BLE001
                texts.append("")
        full = "\n".join(texts)
        return ParsedPdf(ok=True, text=full, num_pages=len(reader.pages))
    except Exception as exc:  # noqa: BLE001
        log.warning("PDF parse failed for %s: %s", pdf_path, exc)
        return ParsedPdf(ok=False, reason=str(exc))
