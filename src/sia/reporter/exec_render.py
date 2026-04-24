"""Render ExecBriefData into HTML + PDF."""

from __future__ import annotations

import logging
from pathlib import Path

from sia.reporter.exec_brief import ExecBriefData

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def render_html(brief: ExecBriefData) -> str:
    """Render the briefing HTML via Jinja2.

    Kept synchronous — Jinja rendering is CPU-only and fast.
    """
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    tmpl = env.get_template("exec_brief.html.j2")
    return tmpl.render(brief=brief)


def render_pdf(brief: ExecBriefData) -> bytes:
    """Render briefing as PDF bytes. Requires WeasyPrint (pyproject dep)."""
    from weasyprint import HTML

    html = render_html(brief)
    pdf_bytes = HTML(string=html, base_url=str(_TEMPLATE_DIR)).write_pdf()
    logger.info("exec brief PDF rendered: report_id=%d bytes=%d",
                brief.report_id, len(pdf_bytes or b""))
    return pdf_bytes or b""
