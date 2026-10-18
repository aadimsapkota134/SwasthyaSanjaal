"""Document extraction and deterministic classification for clinical PDFs and slips."""

from __future__ import annotations

from dataclasses import dataclass
import fitz  # PyMuPDF

from backend.nlp.devanagari import fold, tokenize

DIGITAL_PDF_MIN_CHARS = 50
RASTER_DPI = 200

CLASS_PRESCRIPTION = "prescription"
CLASS_LAB_REPORT = "lab_report"
CLASS_BILL = "bill"
CLASS_NOTE = "note"
CLASS_FCHV_ASSESSMENT = "fchv_assessment"

_MARKERS: dict[str, frozenset[str]] = {
    CLASS_LAB_REPORT: frozenset(
        {
            "cbc", "hb", "hba1c", "haemoglobin", "hemoglobin", "wbc", "rbc",
            "platelet", "creatinine", "widal", "ns1", "esr", "urea", "report",
            "result", "specimen", "reference", "रिपोर्ट", "परीक्षण", "नतिजा",
            "जाँच", "प्रयोगशाला",
        }
    ),
    CLASS_PRESCRIPTION: frozenset(
        {
            "rx", "tab", "tabs", "cap", "caps", "syrup", "syp", "inj", "od",
            "bd", "tds", "qid", "sos", "stat", "dose", "औषधि", "खानु",
            "खानुहोस्", "मात्रा", "चिकित्सक", "सल्लाह",
        }
    ),
    CLASS_BILL: frozenset(
        {
            "bill", "invoice", "receipt", "total", "amount", "charge", "charges",
            "payable", "npr", "rs", "रु", "बिल", "जम्मा", "रकम", "भुक्तानी",
        }
    ),
}


@dataclass(frozen=True, slots=True)
class PdfText:
    text: str
    pages: int
    is_digital: bool


def extract_pdf_text(data: bytes) -> PdfText:
    """Extract text layer from digital PDF using PyMuPDF.

    Digital PDFs are extracted instantly with zero model calls.
    """
    with fitz.open(stream=data, filetype="pdf") as doc:
        pages = [page.get_text() for page in doc]
        count = doc.page_count
    text = "\n".join(pages).strip()
    return PdfText(text=text, pages=count, is_digital=len(text) >= DIGITAL_PDF_MIN_CHARS)


def render_pdf_page(data: bytes, page_number: int = 0, dpi: int = RASTER_DPI) -> bytes:
    """Rasterize one page to PNG image bytes for visual OCR."""
    with fitz.open(stream=data, filetype="pdf") as doc:
        if page_number >= doc.page_count:
            raise ValueError(f"page {page_number} of a {doc.page_count}-page document")
        return doc[page_number].get_pixmap(dpi=dpi).tobytes("png")


@dataclass(frozen=True, slots=True)
class Classification:
    document_class: str
    evidence: tuple[str, ...] = ()


def classify_document(text: str) -> Classification:
    """Classify clinical document type based on vocabulary markers."""
    tokens = {fold(token.text) for token in tokenize(text)}
    scores = {
        name: tuple(sorted(tokens & markers)) for name, markers in _MARKERS.items()
    }
    best = max(scores.items(), key=lambda item: (len(item[1]), -len(item[0])))
    if not best[1]:
        return Classification(document_class=CLASS_NOTE)
    return Classification(document_class=best[0], evidence=best[1])
