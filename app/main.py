from fastapi import FastAPI, UploadFile, File
from .extractor import extract_document
from .rules import run_rules
from .scoring import score_issues, risk_band
from .schemas import RiskReport

app = FastAPI(title="Trade Doc AI MVP")

@app.post("/v1/analyze", response_model=RiskReport)
async def analyze(
    invoice: UploadFile = File(...),
    packing_list: UploadFile = File(...),
    bill_of_lading: UploadFile = File(...)
):
    inv = extract_document("invoice", await invoice.read())
    pack = extract_document("packing_list", await packing_list.read())
    bl = extract_document("bill_of_lading", await bill_of_lading.read())

    issues = run_rules(inv, pack, bl)
    score = score_issues(issues)

    return {
        "route": {"origin_country": "IN", "destination_country": "AE"},
        "risk_score": score,
        "risk_band": risk_band(score),
        "issues": issues,
        "extracted_summary": {
            "invoice": inv,
            "packing_list": pack,
            "bill_of_lading": bl
        }
    }
