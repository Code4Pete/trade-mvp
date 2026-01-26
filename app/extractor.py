# app/extractor.py
# Regex-upgraded, "real text" extractor (no OpenAI calls)
# - Extracts text via pypdf; falls back to OCR if available + low text
# - Uses stronger regex for Invoice / Packing List / Bill of Lading
# - Returns consistent schema + debug helpers (via extract_document_with_debug)

import io
import re
import shutil
from typing import Any, Dict, Optional, Tuple, List

from pypdf import PdfReader

# Optional OCR (works only if poppler + tesseract exist in the runtime)
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


def ocr_pdf(file_bytes: bytes, max_pages: int = 3, dpi: int = 220) -> str:
    """OCR scanned PDFs (requires poppler + tesseract)."""
    if not OCR_AVAILABLE:
        return ""
    images = convert_from_bytes(file_bytes, dpi=dpi)
    texts: List[str] = []
    for img in images[:max_pages]:
        texts.append(pytesseract.image_to_string(img))
    return "\n".join(texts).strip()


def _normalize_text(text: str) -> str:
    # Normalize common OCR/PDF quirks: weird spaces, repeated whitespace, non-breaking spaces
    text = (text or "").replace("\u00a0", " ")
    # Keep newlines (useful for label-based regex), but normalize runs
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def get_document_text(file_bytes: bytes) -> Tuple[str, str]:
    """
    Returns (text, method) where method is:
    - "pdf_text" or "ocr" or "empty"
    """
    text = _normalize_text(extract_pdf_text(file_bytes))

    # If text is very short, try OCR if available
    if len(text) < 350 and OCR_AVAILABLE:
        try:
            ocr_text = _normalize_text(ocr_pdf(file_bytes))
            if len(ocr_text) > len(text):
                return ocr_text, "ocr"
        except Exception:
            pass

    if text:
        return text, "pdf_text"
    return "", "empty"


# ---------------------------
# Regex helpers
# ---------------------------

def _find_first(patterns: List[str], text: str) -> Optional[str]:
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE | re.MULTILINE)
        if m:
            val = m.group(1).strip()
            return val if val else None
    return None


def _clean_id(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    s = s.strip()
    # Remove trailing punctuation
    s = re.sub(r"[^\w\-\/]+$", "", s)
    return s or None


def _to_float(s: Optional[str]) -> Optional[float]:
    if not s:
        return None
    # Remove currency symbols and spaces; keep digits, comma, dot
    s = s.strip()
    s = re.sub(r"[^\d\.,\-+]", "", s)
    if not s:
        return None
    # If commas are thousands separators, remove them
    # (basic heuristic: if both comma and dot exist, treat comma as thousands)
    if "," in s and "." in s:
        s = s.replace(",", "")
    else:
        # If only commas and no dots, could be "5,000" => 5000
        s = s.replace(",", "")
    try:
        return float(s)
    except Exception:
        return None


def _to_int(s: Optional[str]) -> Optional[int]:
    if not s:
        return None
    s = s.strip()
    s = re.sub(r"[^\d]", "", s)
    return int(s) if s else None


def _guess_currency(text: str) -> Optional[str]:
    # Prefer explicit 3-letter currency
    cur = _find_first([r"\bCurrency\s*[:#]?\s*([A-Z]{3})\b"], text)
    if cur:
        return cur.upper()
    for c in ["USD", "AED", "INR", "EUR", "GBP", "SAR", "OMR", "QAR"]:
        if re.search(rf"\b{c}\b", text, flags=re.IGNORECASE):
            return c
    return None


def _guess_incoterm(text: str) -> Optional[str]:
    incos = ["EXW", "FCA", "CPT", "CIP", "DAP", "DPU", "DDP", "FOB", "CFR", "CIF"]
    for t in incos:
        if re.search(rf"\b{t}\b", text, flags=re.IGNORECASE):
            return t
    return None


def _extract_weight_value(text: str, label: str) -> Optional[float]:
    """
    Extract weight after a label like 'Gross Weight' or 'Net Weight'.
    Handles: "Gross Weight: 1200 KG" / "Gross Weight 1,200 KGS" / "Gross Weight 1200"
    """
    pat = rf"{label}\s*[:\-]?\s*([\d\.,]+)"
    m = re.search(pat, text, flags=re.IGNORECASE)
    if not m:
        return None
    return _to_float(m.group(1))


def _extract_qty_value(text: str) -> Optional[int]:
    """
    Extract quantity in multiple forms:
    - "Quantity: 1000 Pieces"
    - "Total Quantity 1,000"
    - "Qty: 1000"
    """
    qty_s = _find_first(
        [
            r"\bTotal\s+Quantity\s*[:\-]?\s*([\d,]+)\b",
            r"\bQuantity\s*[:\-]?\s*([\d,]+)\b",
            r"\bQty\s*[:\-]?\s*([\d,]+)\b",
        ],
        text,
    )
    return _to_int(qty_s)


def _extract_packages(text: str) -> Optional[int]:
    """
    Extract packages/cartons:
    - "No. of Cartons: 50"
    - "No of Packages 50"
    - "Packages: 50 Cartons"
    """
    pkg_s = _find_first(
        [
            r"\bNo\.?\s*of\s*Cartons\s*[:\-]?\s*([\d,]+)\b",
            r"\bNo\.?\s*of\s*Packages\s*[:\-]?\s*([\d,]+)\b",
            r"\bCartons\s*[:\-]?\s*([\d,]+)\b",
            r"\bPackages\s*[:\-]?\s*([\d,]+)\b",
        ],
        text,
    )
    return _to_int(pkg_s)


def _extract_party(text: str, labels: List[str]) -> Optional[str]:
    # Try label-based extraction: "Exporter: ...", "Shipper: ..."
    for lab in labels:
        m = re.search(rf"\b{lab}\s*[:\-]\s*(.+)", text, flags=re.IGNORECASE)
        if m:
            # Stop at newline
            val = m.group(1).strip().split("\n")[0].strip()
            return val or None
    return None


# ---------------------------
# Field extraction (per doc)
# ---------------------------

def extract_fields(doc_type: str, text: str) -> Dict[str, Any]:
    """
    Real extraction using regex/heuristics.
    Returns a stable structure your rules/report expect.
    """
    doc_type = (doc_type or "").lower()
    text = text or ""

    incoterm = _guess_incoterm(text)

    if doc_type == "invoice":
        invoice_no = _clean_id(
            _find_first(
                [
                    r"\bInvoice\s*(?:No|Number)\s*[:#\-]?\s*([A-Z0-9][A-Z0-9\-\/]+)\b",
                    r"\bInv\s*(?:No|Number)\s*[:#\-]?\s*([A-Z0-9][A-Z0-9\-\/]+)\b",
                ],
                text,
            )
        )

        currency = _guess_currency(text)

        # Total amount patterns:
        # "Total Amount: USD 5,000" / "Total Amount USD 5000" / "Total: 5000"
        total_amount_s = _find_first(
            [
                r"\bTotal\s*Amount\s*[:\-]?\s*(?:[A-Z]{3}\s*)?([\d,]+\.\d+|[\d,]+)\b",
                r"\bGrand\s*Total\s*[:\-]?\s*(?:[A-Z]{3}\s*)?([\d,]+\.\d+|[\d,]+)\b",
                r"\bTotal\s*[:\-]?\s*(?:[A-Z]{3}\s*)?([\d,]+\.\d+|[\d,]+)\b",
            ],
            text,
        )

        qty = _extract_qty_value(text)

        exporter = _extract_party(text, ["Exporter", "Seller", "Shipper"])
        importer = _extract_party(text, ["Importer", "Buyer", "Consignee"])

        return {
            "doc_type": "invoice",
            "parties": {
                "exporter": {"name": exporter} if exporter else {},
                "importer": {"name": importer} if importer else {},
            },
            "commercial_terms": {
                "invoice_number": invoice_no,
                "incoterm": incoterm,
                "invoice_value": _to_float(total_amount_s),
                "currency": currency,
            },
            "cargo": {
                "total_quantity": qty,
                "items": [],  # keep empty for MVP; later add table extraction
            },
            "transport": {},
        }

    if doc_type == "packing_list":
        pl_no = _clean_id(
            _find_first(
                [
                    r"\bPacking\s*List\s*(?:No|Number)\s*[:#\-]?\s*([A-Z0-9][A-Z0-9\-\/]+)\b",
                    r"\bP\/L\s*(?:No|Number)\s*[:#\-]?\s*([A-Z0-9][A-Z0-9\-\/]+)\b",
                    r"\bPL\s*(?:No|Number)\s*[:#\-]?\s*([A-Z0-9][A-Z0-9\-\/]+)\b",
                ],
                text,
            )
        )

        qty = _extract_qty_value(text)
        cartons = _extract_packages(text)
        gross = _extract_weight_value(text, "Gross\\s*Weight")
        net = _extract_weight_value(text, "Net\\s*Weight")

        exporter = _extract_party(text, ["Exporter", "Seller", "Shipper"])
        importer = _extract_party(text, ["Importer", "Buyer", "Consignee"])

        return {
            "doc_type": "packing_list",
            "parties": {
                "exporter": {"name": exporter} if exporter else {},
                "importer": {"name": importer} if importer else {},
            },
            "commercial_terms": {"packing_list_number": pl_no},
            "cargo": {
                "total_quantity": qty,
                "total_packages": cartons,
                "total_gross_weight": gross,
                "total_net_weight": net,
                "items": [],
            },
            "transport": {},
        }

    # bill_of_lading
    bl_no = _clean_id(
        _find_first(
            [
                r"\bB\/L\s*(?:No|Number)\s*[:#\-]?\s*([A-Z0-9][A-Z0-9\-\/]+)\b",
                r"\bBL\s*(?:No|Number)\s*[:#\-]?\s*([A-Z0-9][A-Z0-9\-\/]+)\b",
                r"\bBill\s*of\s*Lading\s*(?:No|Number)\s*[:#\-]?\s*([A-Z0-9][A-Z0-9\-\/]+)\b",
            ],
            text,
        )
    )

    packages = _extract_packages(text)
    gross = _extract_weight_value(text, "Gross\\s*Weight")

    freight_terms = _find_first(
        [
            r"\bFreight\s*[:\-]?\s*(Prepaid|Collect)\b",
            r"\bFreight\s*Terms\s*[:\-]?\s*([A-Za-z ]+)\b",
        ],
        text,
    )
    if freight_terms:
        freight_terms = freight_terms.strip()

    pol = _find_first([r"\bPort\s*of\s*Loading\s*[:\-]?\s*(.+)"], text)
    pod = _find_first([r"\bPort\s*of\s*Discharge\s*[:\-]?\s*(.+)"], text)
    # Cut ports at newline if needed
    if pol:
        pol = pol.split("\n")[0].strip()
    if pod:
        pod = pod.split("\n")[0].strip()

    shipper = _extract_party(text, ["Shipper", "Exporter"])
    consignee = _extract_party(text, ["Consignee", "Importer"])

    mode = None
    if re.search(r"\bVessel\b|\bPort\b|\bBill of Lading\b", text, re.IGNORECASE):
        mode = "SEA"

    return {
        "doc_type": "bill_of_lading",
        "parties": {
            "shipper": {"name": shipper} if shipper else {},
            "consignee": {"name": consignee} if consignee else {},
        },
        "commercial_terms": {"freight_terms": freight_terms},
        "cargo": {
            "total_packages": packages,
            "total_gross_weight": gross,
            "items": [],
        },
        "transport": {
            "bl_number": bl_no,
            "mode": mode,
            "port_of_loading": pol,
            "port_of_discharge": pod,
        },
    }


# ---------------------------
# Main entry used by API
# ---------------------------

def extract_document(doc_type: str, file_bytes: bytes) -> Dict[str, Any]:
    """Used by FastAPI endpoints."""
    text, _method = get_document_text(file_bytes)
    return extract_fields(doc_type, text)


def extract_document_with_debug(doc_type: str, file_bytes: bytes) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Returns (extracted_data, debug_info)
    debug_info includes preview + stats so you can verify the PDF text is being used.
    """
    text, method = get_document_text(file_bytes)
    data = extract_fields(doc_type, text)

    # Track which key fields were found (helps explain "—" in report)
    doc_type_l = (doc_type or "").lower()
    fields_found: Dict[str, bool] = {}

    if doc_type_l == "invoice":
        ct = data.get("commercial_terms") or {}
        cargo = data.get("cargo") or {}
        fields_found = {
            "invoice_number": bool(ct.get("invoice_number")),
            "incoterm": bool(ct.get("incoterm")),
            "invoice_value": ct.get("invoice_value") is not None,
            "currency": bool(ct.get("currency")),
            "total_quantity": cargo.get("total_quantity") is not None,
        }
    elif doc_type_l == "packing_list":
        cargo = data.get("cargo") or {}
        ct = data.get("commercial_terms") or {}
        fields_found = {
            "packing_list_number": bool(ct.get("packing_list_number")),
            "total_quantity": cargo.get("total_quantity") is not None,
            "total_packages": cargo.get("total_packages") is not None,
            "total_gross_weight": cargo.get("total_gross_weight") is not None,
            "total_net_weight": cargo.get("total_net_weight") is not None,
        }
    else:
        tr = data.get("transport") or {}
        cargo = data.get("cargo") or {}
        ct = data.get("commercial_terms") or {}
        fields_found = {
            "bl_number": bool(tr.get("bl_number")),
            "port_of_loading": bool(tr.get("port_of_loading")),
            "port_of_discharge": bool(tr.get("port_of_discharge")),
            "freight_terms": bool(ct.get("freight_terms")),
            "total_packages": cargo.get("total_packages") is not None,
            "total_gross_weight": cargo.get("total_gross_weight") is not None,
        }

    debug = {
        "doc_type": doc_type,
        "ocr_available": OCR_AVAILABLE,
        "extraction_method": method,
        "text_chars": len(text or ""),
        "text_preview": (text or "")[:1500],
        "fields_found": fields_found,
    }
    return data, debug
