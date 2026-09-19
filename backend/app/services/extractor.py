"""Pull plain text out of uploaded PDF / DOCX / TXT material."""
import re
from pathlib import Path


def _from_pdf(path: Path) -> str:
    import pdfplumber

    chunks = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            chunks.append(page.extract_text() or "")
    return "\n".join(chunks)


def _from_docx(path: Path) -> str:
    import docx

    document = docx.Document(str(path))
    parts = [p.text for p in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            parts.append(" ".join(cell.text for cell in row.cells))
    return "\n".join(parts)


def clean(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"-\n(\w)", r"\1", text)          # join hyphen-broken words
    text = re.sub(r"\n{2,}", "\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"(?im)^\s*page\s+\d+\s+of\s+\d+\s*$", "", text)
    return text.strip()


def extract_text(path: str | Path) -> str:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        raw = _from_pdf(path)
    elif suffix in (".docx", ".doc"):
        raw = _from_docx(path)
    elif suffix in (".txt", ".md"):
        raw = path.read_text(encoding="utf-8", errors="ignore")
    else:
        raise ValueError(f"Unsupported file type: {suffix}")
    return clean(raw)
