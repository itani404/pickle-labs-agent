"""Business knowledge: the summary and the PDF profile, loaded once (notebook section 2, cell 6).

The whole knowledge (about 1,700 tokens) goes straight into the system prompt, so there is no retrieval.
"""

import re
import unicodedata

from pypdf import PdfReader

from . import config


def load_summary(path=None):
    return (path or config.ME_DIR / "business_summary.txt").read_text(encoding="utf-8").strip()


def load_pdf_text(path=None):
    reader = PdfReader(path or config.ME_DIR / "about_business.pdf")
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    text = unicodedata.normalize("NFKC", text)      # turns ligatures such as the "fi" glyph into plain letters
    return re.sub(r"[ \t]+\n", "\n", text).strip()


BUSINESS_SUMMARY = load_summary()
BUSINESS_PDF = load_pdf_text()
