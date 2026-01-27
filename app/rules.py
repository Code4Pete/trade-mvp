import re
from typing import List, Dict, Any, Optional
from .schemas import Issue

def _safe_float(x) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None

def _pct_diff(a: float, b: float) -> float:
    denom = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / denom * 100.0

def _hs_valid(hs: Optional[str]) -> bool:
    if not hs:
        return False
    hs = hs.strip().replace(".", "")
    return bool(re.fullmatch(r"\d{6,10}", hs))

def run_rules(inv: Dict[str, Any], pack: Dict[str, Any], bl: Dict[str, Any]) -> List[Issue]:
    """
    India -> UAE (UAE-first) v1 rules.
    These are intentionally simple + explainable for brokers.
    """
    issues: List[Issue] = []

        # 0) Certificate of Origin (COO) missing / not referenced (critical)
    ct = inv.get("commercial_terms") or {}
    coo_country = ct.get("country_of_origin")
    coo_mention = ct.get("coo_mention")

    # Missing if neither a COO country nor any "Certificate of Origin/COO" mention exists
    if not coo_country and not coo_mention:
        issues.append(Issue(
            severity="critical",
            code="COO_MISSING",
            title="Certificate of Origin missing / not referenced",
            explanation="For India→UAE shipments, COO is commonly required to claim CEPA duty benefits and avoid customs queries.",
            recommendation="Include a valid Certificate of Origin (or reference it clearly) and ensure COO details match invoice and packing list.",
            evidence={
                "invoice_country_of_origin": coo_country,
                "invoice_coo_mention": coo_mention,
            }
        ))

    # 1) Incoterm missing (critical)
    incoterm = (inv.get("commercial_terms") or {}).get("incoterm")
    if not incoterm:
        issues.append(Issue(
            severity="critical",
            code="INCOTERM_MISSING",
            title="Incoterm missing on commercial invoice",
            explanation="Incoterms affect valuation and responsibility; missing Incoterms often trigger customs queries.",
            recommendation="Add Incoterm (e.g., FOB/CIF/EXW) on the invoice and ensure it matches the booking.",
            evidence={}
        ))

    # 2) Quantity mismatch invoice vs packing list (critical)
    inv_qty = _safe_float((inv.get("cargo") or {}).get("total_quantity"))
    pack_qty = _safe_float((pack.get("cargo") or {}).get("total_quantity"))
    if inv_qty is not None and pack_qty is not None and inv_qty != pack_qty:
        issues.append(Issue(
            severity="critical",
            code="QTY_MISMATCH_INV_PACK",
            title="Total quantity mismatch between invoice and packing list",
            explanation="Customs compares quantities across documents; mismatches frequently cause holds or amendments.",
            recommendation="Align quantities on invoice and packing list. If partial shipment, reflect that consistently.",
            evidence={"invoice_total_quantity": inv_qty, "packing_total_quantity": pack_qty}
        ))

    # 3) Gross weight mismatch packing list vs BL > 2% (critical)
    pack_gw = _safe_float((pack.get("cargo") or {}).get("total_gross_weight"))
    bl_gw = _safe_float((bl.get("cargo") or {}).get("total_gross_weight"))
    if pack_gw is not None and bl_gw is not None:
        diff = _pct_diff(pack_gw, bl_gw)
        if diff > 2.0:
            issues.append(Issue(
                severity="critical",
                code="GW_MISMATCH_PACK_BL",
                title="Gross weight mismatch between packing list and Bill of Lading",
                explanation="Carrier BL weight should align with packing weights; large deltas trigger inspection or BL amendment.",
                recommendation="Confirm weighment and amend BL or packing list before filing.",
                evidence={"packing_gross_weight": pack_gw, "bl_gross_weight": bl_gw, "pct_diff": round(diff, 2)}
            ))

    # 4) HS codes missing/invalid (high) — check at least one item
    items = (inv.get("cargo") or {}).get("items") or []
    if items:
        invalid = 0
        for it in items:
            if not _hs_valid((it or {}).get("hs_code")):
                invalid += 1
        if invalid == len(items):
            issues.append(Issue(
                severity="high",
                code="HS_ALL_MISSING_OR_INVALID",
                title="HS codes missing or invalid for invoice items",
                explanation="HS codes drive duty, restrictions, and clearance logic. Missing/invalid HS codes often cause queries.",
                recommendation="Add correct HS codes (6–10 digits) aligned to product descriptions.",
                evidence={"items_count": len(items), "invalid_count": invalid}
            ))
    else:
        issues.append(Issue(
            severity="high",
            code="NO_ITEMS_EXTRACTED",
            title="No line items extracted from invoice",
            explanation="Without item lines, HS/quantity/value checks cannot run reliably.",
            recommendation="Upload a clearer invoice (or we will improve OCR/extraction).",
            evidence={}
        ))

    return issues
