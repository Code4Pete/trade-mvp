import os
import io
import json
from typing import Dict, Any
from pypdf import PdfReader

# Optional OCR imports (may not work until we install system packages)
try:
    from pdf2image import convert_from_bytes
    import pytesseract
    OCR_AVAILABLE = True
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
    """
    OCR scanned PDFs (works once poppler + tesseract are installed).
    If OCR isn't available, returns empty string.
    """
    if not OCR_AVAILABLE:
        return ""

    images = convert_from_bytes(file_bytes, dpi=dpi)
    texts = []
    for img in images[:max_pages]:
        texts.append(pytesseract.image_to_string(img))
    return "\n".join(texts).strip()


def get_document_text(file_bytes: bytes) -> str:
    """Hybrid extraction: try PDF text first, then OCR if needed."""
    text = extract_pdf_text(file_bytes)
    if len(text) < 400:  # heuristic: scanned/low-text PDFs
        text = ocr_pdf(file_bytes)
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
    Uses OpenAI if OPENAI_API_KEY is set.
    Otherwise returns a demo stub.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return demo_stub_extract(doc_type)

    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    schema_hint = {
        "doc_type": doc_type,
        "parties": {
            "exporter": {"name": None, "address": None, "country": None},
            "importer": {"name": None, "address": None, "country": None},
            "shipper": {"name": None, "address": None, "country": None},
            "consignee": {"name": None, "address": None, "country": None},
        },
        "commercial_terms": {
            "invoice_number": None,
            "invoice_date": None,
            "incoterm": None,
            "currency": None,
            "invoice_value": None,
        },
        "cargo": {
            "items": [{"description": None, "hs_code": None, "quantity": None, "unit": None}],
            "total_quantity": None,
            "total_gross_weight": None,
            "total_net_weight": None,
        },
        "transport": {"mode": None, "bl_number": None, "carrier": None, "port_of_loading": None, "port_of_discharge": None},
    }

    developer = (
        "You are a customs documentation expert. "
        "Extract shipment data from the document text. "
        "Return ONLY valid JSON. "
        "Do not guess: use null when missing. "
        "HS code must be 6-10 digits (no punctuation). "
        "Prefer ISO2 country codes (IN, AE)."
    )

    user = (
        f"Document type: {doc_type}\n"
        f"Return JSON matching this schema:\n{json.dumps(schema_hint)}\n\n"
        f"Document text:\n{doc_text[:12000]}"
    )

    resp = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {"role": "developer", "content": developer},
            {"role": "user", "content": user},
        ],
    )

    raw = resp.output_text.strip().replace("```json", "").replace("```", "").strip()
    data = json.loads(raw)
    data["doc_type"] = doc_type
    return data


def extract_document(doc_type: str, file_bytes: bytes) -> Dict[str, Any]:
    text = get_document_text(file_bytes)
    return llm_extract(doc_type, text)
