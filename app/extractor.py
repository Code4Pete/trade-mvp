import os
import io
import json
from typing import Dict, Any
from pypdf import PdfReader

# Optional OCR imports (only work if poppler + tesseract are installed)
import shutil

try:
    from pdf2image import convert_from_bytes
    import pytesseract
    OCR_AVAILABLE = shutil.which("tesseract") is not None
except Exception:
    OCR_AVAILABLE = False


def extract_pdf_text(file_bytes: bytes) -> str:
    """Extract selectable text from PDF pages (works for digital PDFs)."""
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        parts = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        return "\n".join(parts).strip()
    except Exception:
        return ""


def ocr_pdf(file_bytes: bytes, max_pages: int = 5, dpi: int = 200) -> str:
    """OCR scanned PDFs (requires poppler + tesseract)."""
    if not OCR_AVAILABLE:
        return ""
    images = convert_from_bytes(file_bytes, dpi=dpi)
    texts = []
    for img in images[:max_pages]:
        texts.append(pytesseract.image_to_string(img))
    return "\n".join(texts).strip()


def get_document_text(file_bytes: bytes) -> str:
    text = extract_pdf_text(file_bytes)

    # Only attempt OCR if:
    # 1) text is small AND
    # 2) OCR is available (tesseract installed)
    if len(text) < 400 and OCR_AVAILABLE:
        try:
            text = ocr_pdf(file_bytes)
        except Exception:
            pass  # fail silently in prod

    return text


def demo_stub_extract(doc_type: str) -> Dict[str, Any]:
    """Fallback if OPENAI_API_KEY not set (keeps app runnable)."""
    if doc_type == "invoice":
        return {
            "doc_type": "invoice",
            "parties": {
                "exporter": {"name": "ACME EXPORTS PVT LTD", "address": "Mumbai, India", "country": "IN"},
                "importer": {"name": "GULF TRADING LLC", "address": "Dubai, UAE", "country": "AE"},
            },
            "commercial_terms": {"invoice_number": "INV-1007", "incoterm": "FOB", "invoice_value": 25000.0},
            "cargo": {"items": [{"description": "Aluminium brackets", "hs_code": "761699"}], "total_quantity": 1200},
            "transport": {},
        }

    if doc_type == "packing_list":
        return {
            "doc_type": "packing_list",
            "parties": {},
            "commercial_terms": {},
            "cargo": {"items": [], "total_quantity": 1000, "total_gross_weight": 950.0},
            "transport": {},
        }

    return {
        "doc_type": "bill_of_lading",
        "parties": {"shipper": {"name": "ACME EXPORTS PVT LTD", "country": "IN"}},
        "commercial_terms": {},
        "cargo": {"total_gross_weight": 900.0},
        "transport": {"bl_number": "BL-778899", "mode": "SEA"},
    }


def llm_extract(doc_type: str, doc_text: str) -> Dict[str, Any]:
    """
    DEMO MODE:
    Always return stub data (no OpenAI calls).
    """
    return demo_stub_extract(doc_type)


def extract_document(doc_type: str, file_bytes: bytes) -> Dict[str, Any]:
    text = get_document_text(file_bytes)
    return llm_extract(doc_type, text)
