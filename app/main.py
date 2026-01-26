from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse

from .extractor import extract_document_with_debug
from .rules import run_rules
from .scoring import score_issues, risk_band
from .schemas import RiskReport
from .report import html_response

app = FastAPI(title="Trade Doc AI MVP")

# In-memory store for latest report (MVP only)
LAST_REPORT = None


# ---------------------------
# API: Analyze (JSON)
# ---------------------------
@app.post("/v1/analyze", response_model=RiskReport)
async def analyze(
    invoice: UploadFile = File(...),
    packing_list: UploadFile = File(...),
    bill_of_lading: UploadFile = File(...),
):
    inv, inv_dbg = extract_document_with_debug("invoice", await invoice.read())
    pack, pack_dbg = extract_document_with_debug("packing_list", await packing_list.read())
    bl, bl_dbg = extract_document_with_debug("bill_of_lading", await bill_of_lading.read())

    issues = run_rules(inv, pack, bl)
    score = score_issues(issues)
    issues_for_report = [i.model_dump() for i in issues]

    result = {
        "route": {"origin_country": "IN", "destination_country": "AE"},
        "risk_score": score,
        "risk_band": risk_band(score),
        "issues": issues_for_report,
        "extracted_summary": {
            "invoice": inv,
            "packing_list": pack,
            "bill_of_lading": bl,
        },
        "debug": {
            "invoice": inv_dbg,
            "packing_list": pack_dbg,
            "bill_of_lading": bl_dbg,
        },
    }

    global LAST_REPORT
    LAST_REPORT = result
    return result


# ---------------------------
# API: Analyze + redirect
# ---------------------------
@app.post("/v1/analyze-and-view")
async def analyze_and_view(
    invoice: UploadFile = File(...),
    packing_list: UploadFile = File(...),
    bill_of_lading: UploadFile = File(...),
):
    inv, inv_dbg = extract_document_with_debug("invoice", await invoice.read())
    pack, pack_dbg = extract_document_with_debug("packing_list", await packing_list.read())
    bl, bl_dbg = extract_document_with_debug("bill_of_lading", await bill_of_lading.read())

    issues = run_rules(inv, pack, bl)
    score = score_issues(issues)
    issues_for_report = [i.model_dump() for i in issues]

    result = {
        "route": {"origin_country": "IN", "destination_country": "AE"},
        "risk_score": score,
        "risk_band": risk_band(score),
        "issues": issues_for_report,
        "extracted_summary": {
            "invoice": inv,
            "packing_list": pack,
            "bill_of_lading": bl,
        },
        "debug": {
            "invoice": inv_dbg,
            "packing_list": pack_dbg,
            "bill_of_lading": bl_dbg,
        },
    }

    global LAST_REPORT
    LAST_REPORT = result

    return RedirectResponse(url="/report", status_code=303)


# ---------------------------
# HTML: Report
# ---------------------------
@app.get("/report")
def report():
    if not LAST_REPORT:
        return HTMLResponse("<h2>No report yet</h2><p>Run an analysis first.</p>", status_code=200)
    return html_response(LAST_REPORT)


# ---------------------------
# HTML: Analyze UI
# ---------------------------
@app.get("/analyze")
def analyze_ui():
    return HTMLResponse(
        """
    <!doctype html>
    <html>
    <head>
      <title>Run Analysis</title>
      <style>
        body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial; background:#0b1220; color:#e5e7eb; margin:0; padding:40px; }
        .card { max-width:720px; margin:auto; background:#0f172a; border:1px solid #24304e; border-radius:16px; padding:24px; }
        h1 { margin:0 0 8px; }
        .muted { color:#9ca3af; margin:0 0 18px; }
        label { display:block; margin:14px 0 6px; font-weight:700; }
        input[type=file] { width:100%; padding:10px; background:#111a2e; border:1px solid #24304e; border-radius:12px; color:#e5e7eb; }
        button { margin-top:18px; padding:12px 14px; border:0; border-radius:12px; background:#2563eb; color:white; font-weight:800; cursor:pointer; }
        button:hover { filter:brightness(1.05); }
        a { color:#93c5fd; }
      </style>
    </head>
    <body>
      <div class="card">
        <h1>Run document analysis</h1>
        <p class="muted">Upload Invoice, Packing List, and Bill of Lading.</p>

        <form action="/v1/analyze-and-view" method="post" enctype="multipart/form-data">
          <label>Invoice (PDF)</label>
          <input type="file" name="invoice" accept="application/pdf" required>

          <label>Packing List (PDF)</label>
          <input type="file" name="packing_list" accept="application/pdf" required>

          <label>Bill of Lading (PDF)</label>
          <input type="file" name="bill_of_lading" accept="application/pdf" required>

          <button type="submit">Analyze & View Report →</button>
        </form>

        <p class="muted" style="margin-top:16px;"><a href="/">← Back to home</a></p>
      </div>
    </body>
    </html>
    """
    )


# ---------------------------
# HTML: Home
# ---------------------------
@app.get("/")
def home():
    return HTMLResponse(
        """
    <!doctype html>
    <html>
    <head>
      <title>Trade Doc AI MVP</title>
      <style>
        body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial; background:#0b1220; color:#e5e7eb; margin:0; padding:40px; }
        .card { max-width:600px; margin:auto; background:#0f172a; border:1px solid #24304e; border-radius:16px; padding:24px; }
        a { display:block; margin:12px 0; padding:12px; background:#1f2937; border-radius:10px; color:#93c5fd; text-decoration:none; font-weight:600; }
        a:hover { background:#111827; }
        .muted { color:#9ca3af; font-size:14px; }
      </style>
    </head>
    <body>
      <div class="card">
        <h1>Trade Doc AI MVP</h1>
        <p class="muted">Pre-filing risk checks for export documentation</p>

        <a href="/analyze">▶ Run document analysis</a>
        <a href="/report">📄 View latest risk report</a>
        <a href="/docs">⚙ API docs</a>
      </div>
    </body>
    </html>
    """
    )
