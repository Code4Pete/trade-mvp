import io
import os
import re
import shutil
from typing import Dict, Any, Optional, Tuple, List

from pypdf import PdfReader

# Optional OCR imports (only work if poppler + tesseract are installed)
try:
    from pdf2image import convert_from_bytes
    import pytesseract

    OCR_AVAILABLE = shutil.which("tesseract") is not None
except Exception:
    OCR_AVAILABLE = False


# ---------------------------
# Text extraction (PDF + OCR)
# ---------------------------

def extract_pdf_text(file_bytes: bytes) -> str:
    """Extract selectable text from PDF pages (digital PDFs)."""
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        parts: List[str] = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        return "\n".join(parts).strip()
    except Exception:
        return ""


def ocr_pdf(file_bytes: bytes, max_pages: int = 3, dpi: int = 200) -> str:
    """OCR scanned PDFs (requires poppler + tesseract)."""
    if not OCR_AVAILABLE:
        return ""
    images = convert_from_bytes(file_bytes, dpi=dpi)
    texts: List[str] = []
    for img in images[:max_pages]:
        texts.append(pytesseract.image_to_string(img))
    return "\n".join(texts).strip()


def get_document_text(file_bytes: bytes) -> str:
    """
    Hybrid extraction:
    - Try PDF text extraction
    - If too little text and OCR is available, OCR first N pages
    """
    text = extract_pdf_text(file_bytes)

    if len(text) < 300 and OCR_AVAILABLE:
        try:
            ocr_text = ocr_pdf(file_bytes)
            if len(ocr_text) > len(text):
                text = ocr_text
        except Exception:
            pass  # fail silently

    return (text or "").strip()


# ---------------------------
# Helpers for parsing
# ---------------------------

def _find(pattern: str, text: str) -> Optional[str]:
    """Return first capture group for regex pattern."""
    m = re.search(pattern, text or "", flags=re.IGNORECASE | re.MULTILINE)
    return m.group(1).strip() if m else None


def _to_int(s: Optional[str]) -> Optional[int]:
    if not s:
        return None
    s2 = re.sub(r"[^\d]", "", s)
    return int(s2) if s2 else None


def _to_float(s: Optional[str]) -> Optional[float]:
    if not s:
        return None
    s2 = s.replace(",", "").strip()
    m = re.search(r"[-+]?\d*\.?\d+", s2)
    return float(m.group(0)) if m else None


def _upper_clean(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    return re.sub(r"\s+", " ", s).strip()


def _guess_incoterm(text: str) -> Optional[str]:
    incos = ["EXW", "FCA", "CPT", "CIP", "DAP", "DPU", "DDP", "FOB", "CFR", "CIF"]
    for t in incos:
        if re.search(rf"\b{t}\b", text or "", flags=re.IGNORECASE):
            return t
    return None


# ---------------------------
# Real extraction (no OpenAI)
# ---------------------------

def extract_fields(doc_type: str, text: str) -> Dict[str, Any]:
    """
    Minimal-but-real extraction using regex/heuristics.
    Cheap to run and good enough for MVP.
    """
    doc_type = (doc_type or "").lower()
    text = text or ""

    incoterm = _guess_incoterm(text)

    # ---------------- INVOICE ----------------
    if doc_type == "invoice":
        invoice_no = (
            _find(r"Invoice\s*(?:No|Number)\s*[:#]?\s*([A-Z0-9\-\/]+)", text)
            or _find(r"\bINV[-\s]*([0-9]{1,10})\b", text)
        )

        currency = (
            _find(r"\bCurrency\s*[:#]?\s*([A-Z]{3})\b", text)
            or ("USD" if re.search(r"\bUSD\b", text, re.IGNORECASE) else None)
            or ("EUR" if re.search(r"\bEUR\b", text, re.IGNORECASE) else None)
        )

        total_amount = (
            _find(r"Total\s*Amount\s*[:#]?\s*(?:USD|INR|AED|EUR|GBP)?\s*([\d,]+\.\d+|[\d,]+)", text)
            or _find(r"Invoice\s*Total\s*[:#]?\s*(?:USD|INR|AED|EUR|GBP)?\s*([\d,]+\.\d+|[\d,]+)", text)
            or _find(r"\bTotal\s*[:#]?\s*(?:USD|INR|AED|EUR|GBP)?\s*([\d,]+\.\d+|[\d,]+)", text)
        )

        qty = (
            _find(r"\bTotal\s*Quantity\s*[:#]?\s*([\d,]+)", text)
            or _find(r"\bQuantity\s*[:#]?\s*([\d,]+)", text)
        )

        exporter = _find(r"\bSeller\s*[:#]?\s*(.+)", text)
        importer = _find(r"\bBuyer\s*[:#]?\s*(.+)", text)

        return {
            "doc_type": "invoice",
            "parties": {
                "exporter": {"name": _upper_clean(exporter)} if exporter else {},
                "importer": {"name": _upper_clean(importer)} if importer else {},
            },
            "commercial_terms": {
                "invoice_number": invoice_no,
                "incoterm": incoterm,
                "invoice_value": _to_float(total_amount),
                "currency": currency,
            },
            "cargo": {
                "total_quantity": _to_int(qty),
                "items": [],
            },
            "transport": {},
            "raw_text_preview": text[:1200],
        }

    # -------------- PACKING LIST --------------
    if doc_type == "packing_list":
        pl_no = _find(r"Packing\s*List\s*(?:No|Number)\s*[:#]?\s*([A-Z0-9\-\/]+)", text)

        cartons = (
            _find(r"No\.\s*of\s*Cartons\s*[:#]?\s*([\d,]+)", text)
            or _find(r"\bCartons\s*[:#]?\s*([\d,]+)", text)
            or _find(r"\bPackages\s*[:#]?\s*([\d,]+)", text)
        )

        gross = _find(r"Gross\s*Weight\s*[:#]?\s*([\d,\.]+)", text)
        net = _find(r"Net\s*Weight\s*[:#]?\s*([\d,\.]+)", text)

        qty = (
            _find(r"Total\s*Quantity\s*[:#]?\s*([\d,]+)", text)
            or _find(r"\bQuantity\s*[:#]?\s*([\d,]+)", text)
        )

        return {
            "doc_type": "packing_list",
            "parties": {},
            "commercial_terms": {"packing_list_number": pl_no},
            "cargo": {
                "total_quantity": _to_int(qty),
                "total_packages": _to_int(cartons),
                "total_gross_weight": _to_float(gross),
                "total_net_weight": _to_float(net),
                "items": [],
            },
            "transport": {},
            "raw_text_preview": text[:1200],
        }

    # -------------- BILL OF LADING --------------
    bl_no = (
        _find(r"\bB\/L\s*(?:No|Number)\s*[:#]?\s*([A-Z0-9\-\/]+)", text)
        or _find(r"\bBL\s*(?:No|Number)\s*[:#]?\s*([A-Z0-9\-\/]+)", text)
        or _find(r"\bBill\s*of\s*Lading\s*(?:No|Number)\s*[:#]?\s*([A-Z0-9\-\/]+)", text)
    )

    packages = (
        _find(r"No\.\s*of\s*Packages\s*[:#]?\s*([\d,]+)", text)
        or _find(r"\bPackages\s*[:#]?\s*([\d,]+)", text)
    )

    freight = _find(r"\bFreight\s*[:#]?\s*([A-Za-z ]+)", text)
    gross = _find(r"Gross\s*Weight\s*[:#]?\s*([\d,\.]+)", text)

    mode = "SEA" if re.search(r"\bVessel\b|\bPort\b", text, re.IGNORECASE) else None

    return {
        "doc_type": "bill_of_lading",
        "parties": {},
        "commercial_terms": {"freight_terms": _upper_clean(freight)},
        "cargo": {
            "total_packages": _to_int(packages),
            "total_gross_weight": _to_float(gross),
        },
        "transport": {
            "bl_number": bl_no,
            "mode": mode,
        },
        "raw_text_preview": text[:1200],
    }


# ---------------------------
# Main entry used by API
# ---------------------------

def extract_document(doc_type: str, file_bytes: bytes) -> Dict[str, Any]:
    """
    This is what your FastAPI endpoint calls.
    Always extracts real text and parses real fields.
    """
    text = get_document_text(file_bytes)
    return extract_fields(doc_type, text)


def extract_document_with_debug(
    doc_type: str, file_bytes: bytes
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Returns (extracted_data, debug_info)
    debug_info includes preview + stats so you can verify the PDF text is being used.
    """
    text = get_document_text(file_bytes)

    debug = {
        "doc_type": doc_type,
        "ocr_available": OCR_AVAILABLE,
        "text_chars": len(text or ""),
        "text_preview": (text or "")[:1500],
    }

    data = extract_fields(doc_type, text)
    return data, debug
