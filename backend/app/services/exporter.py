"""Render a Paper to DOCX and PDF."""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.config import settings

OPTION_LABELS = ["A", "B", "C", "D", "E", "F"]


def _export_dir() -> Path:
    path = Path(settings.export_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def to_docx(paper) -> str:
    doc = Document()
    doc.styles["Normal"].font.name = "Times New Roman"
    doc.styles["Normal"].font.size = Pt(11)

    head = doc.add_paragraph(paper.institution or "")
    head.alignment = WD_ALIGN_PARAGRAPH.CENTER
    head.runs[0].bold = True if head.runs else None

    sub = doc.add_paragraph(paper.title)
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER

    meta = doc.add_paragraph(
        f"{paper.subject}"
        + (f"  |  {paper.semester}" if paper.semester else "")
        + f"  |  Time: {paper.duration_minutes} min  |  Max marks: {paper.total_marks}"
    )
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER

    if paper.instructions:
        note = doc.add_paragraph(paper.instructions)
        note.runs[0].italic = True

    for section in paper.sections:
        doc.add_paragraph()
        heading = doc.add_paragraph(section.title)
        heading.runs[0].bold = True
        if section.instruction:
            doc.add_paragraph(section.instruction).runs[0].italic = True

        for idx, q in enumerate(section.questions, start=1):
            doc.add_paragraph(f"{idx}. {q.text}    [{q.marks}]")
            for oi, option in enumerate(q.options or []):
                doc.add_paragraph(f"    ({OPTION_LABELS[oi]}) {option}")

    out = _export_dir() / f"paper_{paper.id}.docx"
    doc.save(str(out))
    return str(out)


def to_pdf(paper) -> str:
    out = _export_dir() / f"paper_{paper.id}.pdf"
    doc = SimpleDocTemplate(
        str(out), pagesize=A4,
        leftMargin=2.2 * cm, rightMargin=2.2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
        title=paper.title,
    )
    base = getSampleStyleSheet()
    centre = ParagraphStyle("centre", parent=base["Normal"], alignment=TA_CENTER, fontSize=11)
    title = ParagraphStyle("title", parent=centre, fontSize=13, spaceAfter=2, fontName="Times-Bold")
    body = ParagraphStyle("body", parent=base["Normal"], alignment=TA_JUSTIFY,
                          fontName="Times-Roman", fontSize=11, leading=15, spaceAfter=5)
    sec = ParagraphStyle("sec", parent=body, fontName="Times-Bold", spaceBefore=12)
    note = ParagraphStyle("note", parent=body, fontName="Times-Italic", fontSize=10)

    flow = [Paragraph(paper.institution or "", title),
            Paragraph(paper.title, centre)]
    meta = (f"{paper.subject}"
            + (f" &nbsp;|&nbsp; {paper.semester}" if paper.semester else "")
            + f" &nbsp;|&nbsp; Time: {paper.duration_minutes} min"
              f" &nbsp;|&nbsp; Max marks: {paper.total_marks}")
    flow += [Paragraph(meta, centre), Spacer(1, 10)]
    if paper.instructions:
        flow += [Paragraph(paper.instructions, note), Spacer(1, 6)]

    for section in paper.sections:
        flow.append(Paragraph(section.title, sec))
        if section.instruction:
            flow.append(Paragraph(section.instruction, note))
        for idx, q in enumerate(section.questions, start=1):
            flow.append(Paragraph(f"{idx}. {q.text} &nbsp;&nbsp;<b>[{q.marks}]</b>", body))
            for oi, option in enumerate(q.options or []):
                flow.append(Paragraph(f"&nbsp;&nbsp;&nbsp;({OPTION_LABELS[oi]}) {option}", body))

    doc.build(flow)
    return str(out)


def answer_key_docx(paper) -> str:
    doc = Document()
    doc.add_paragraph(f"{paper.title} — Answer key").runs[0].bold = True
    for section in paper.sections:
        doc.add_paragraph(section.title).runs[0].bold = True
        for idx, q in enumerate(section.questions, start=1):
            doc.add_paragraph(f"{idx}. {q.answer_key or '(open-ended)'}")
    out = _export_dir() / f"paper_{paper.id}_key.docx"
    doc.save(str(out))
    return str(out)
