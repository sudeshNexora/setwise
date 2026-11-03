"""Pull plain text out of uploaded PDF / DOCX / TXT material."""
import re
from collections import Counter
from pathlib import Path


def _normalize_line(line: str) -> str:
    """Page numbers differ per page ('...CEC 1', '...CEC 2'); normalise digits
    so the same running header/footer line still compares equal across pages.
    Internal spacing is also collapsed: PDF text extraction can produce
    slightly different whitespace for a visually identical line on different
    pages (layout-based extraction, not literal repeated characters), which
    would otherwise defeat an exact match even after digits are normalised."""
    line = re.sub(r"\d+", "#", line.strip().lower())
    return re.sub(r"\s+", " ", line)


def _strip_running_headers_footers(pages: list[str], min_pages: int = 3, min_fraction: float = 0.4) -> list[str]:
    """Drop lines that repeat near-identically across many pages — running
    headers, and footers like 'Author Name, Dept of X, <page>'. These are page
    furniture, not content, but with no page-boundary awareness they'd get
    joined into the body text and a name repeated 20+ times outranks almost
    any real sentence in the document for a frequency-based keyword extractor.
    Must run on PER-PAGE text, before pages are joined into one blob — the
    repetition is only visible page by page.
    """
    if len(pages) < min_pages:
        return pages
    def _key(line: str) -> str:
        # Compare only the first ~20 normalised characters, not the whole
        # line. A document stitched together from more than one source
        # (different chapters, different authors, a re-typed section) can
        # have a footer whose WORDING changes partway through — e.g.
        # "Author Name, Dept of X, 4" on early pages vs "Author Name, Asst
        # Prof, Dept of Y, Page 4" on later ones. Both start the same way
        # and diverge after ~20 characters; comparing the full line (or even
        # a 40-char prefix) treats them as two unrelated lines, so NEITHER
        # individually clears the repetition threshold and both leak
        # through. A short prefix unifies them under one key instead.
        return _normalize_line(line)[:20]

    counts = Counter()
    for page_text in pages:
        seen_this_page = set()
        for line in page_text.splitlines():
            if not line.strip():
                continue
            key = _key(line)
            if key and key not in seen_this_page:
                counts[key] += 1
                seen_this_page.add(key)
    threshold = max(min_pages, int(len(pages) * min_fraction))
    repeated = {key for key, c in counts.items() if c >= threshold}
    return [
        "\n".join(ln for ln in page_text.splitlines() if _key(ln) not in repeated or not ln.strip())
        for page_text in pages
    ]


def _from_pdf(path: Path) -> str:
    import pdfplumber

    with pdfplumber.open(str(path)) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    pages = _strip_running_headers_footers(pages)
    return "\n".join(pages)


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
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"(?im)^\s*page\s+\d+\s+of\s+\d+\s*$", "", text)
    # drop figure/table caption lines — "Figure 3.1: ..." reads as a concept
    # to a keyword extractor even though it names a diagram, not a topic.
    text = re.sub(r"(?im)^\s*(fig\.?|figure|table)\s*\d+[:.\-]?.*$", "", text)

    # Drop whole CODE lines too, not just the figure/caption kind. A variable
    # name that happens to be a real English word ("forest = RandomForest...")
    # survives spaCy's noun-chunk filter just fine — POS tagging can't tell
    # "forest" the Python object from "forest" the dictionary word. The only
    # reliable signal is the line's shape, so code is stripped at the line
    # level, here, BEFORE extract_topics ever sees it — not only at the
    # sentence-selection stage in nlp_engine.py, which runs too late to stop
    # a stray identifier from being picked up as a topic in the first place.
    _code_line = re.compile(
        r"(?im)^\s*(?:"
        r"(in|out)\s*\[\s*\d*\s*\]\s*:"      # Jupyter cell markers
        r"|import\s+\w+"
        r"|print\s*\("
        r"|\w+\s*=\s*\w+\("                   # var = Something(
        r"|\w+\.\w+\("                         # obj.method(
        r").*$"
    )
    text = _code_line.sub("", text)
    # PDF line-wrapping leaves a raw newline in the middle of a sentence
    # ("one\nmight think"). The caption/page-number regexes above need real
    # line boundaries to match against, so this flattening runs last: every
    # remaining newline — mid-sentence wrap or paragraph gap alike — becomes
    # a plain space, so no sentence downstream carries an embedded break.
    text = re.sub(r"\n+", " ", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
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
