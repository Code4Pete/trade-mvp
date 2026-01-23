from typing import Dict, Any, List
from fastapi.responses import HTMLResponse

def _badge_color(band: str) -> str:
    band = (band or "").lower()
    if band == "high":
        return "#b91c1c"  # red
    if band == "medium":
        return "#b45309"  # amber
    return "#15803d"      # green

def render_report_html(report: Dict[str, Any]) -> str:
    route = report.get("route", {})
    score = report.get("risk_score", 0)
    band = report.get("risk_band", "low")
    issues: List[Dict[str, Any]] = report.get("issues", [])

    summary = report.get("extracted_summary") or {}
    inv = summary.get("invoice") or {}
    pl = summary.get("packing_list") or {}
    bl = summary.get("bill_of_lading") or {}

    inv_terms = inv.get("commercial_terms") or {}
    inv_no = inv_terms.get("invoice_number") or "—"
    incoterm = inv_terms.get("incoterm") or "—"
    inv_value = inv_terms.get("invoice_value") or "—"

    inv_qty = (inv.get("cargo") or {}).get("total_quantity") or "—"
    pl_qty = (pl.get("cargo") or {}).get("total_quantity") or "—"
    pl_gw = (pl.get("cargo") or {}).get("total_gross_weight") or "—"

    bl_no = (bl.get("transport") or {}).get("bl_number") or "—"
    bl_gw = (bl.get("cargo") or {}).get("total_gross_weight") or "—"


    badge = _badge_color(band)

    issues_html = ""
    if not issues:
        issues_html = "<div class='card ok'>No issues found.</div>"
    else:
        for i, it in enumerate(issues, start=1):
            sev = (it.get("severity") or "low").upper()
            title = it.get("title") or ""
            explanation = it.get("explanation") or ""
            recommendation = it.get("recommendation") or ""

            issues_html += f"""
            <div class="card">
              <div class="row">
                <div class="pill">{sev}</div>
                <div class="h3">{i}. {title}</div>
              </div>
              <div class="muted">{explanation}</div>
              <div class="rec">
                <div class="h4">Fix</div>
                <div>{recommendation}</div>
              </div>
            </div>
            """
    summary_html = f"""
  <div class="section">
    <div class="h2">Extracted summary</div>
    <div class="card">
      <div class="row"><div class="pill">Invoice</div></div>
      <div class="muted">
        <b>Invoice #:</b> {inv_no} &nbsp; | &nbsp;
        <b>Incoterm:</b> {incoterm} &nbsp; | &nbsp;
        <b>Value:</b> {inv_value} &nbsp; | &nbsp;
        <b>Qty:</b> {inv_qty}
      </div>
    </div>

    <div class="card">
      <div class="row"><div class="pill">Packing List</div></div>
      <div class="muted">
        <b>Qty:</b> {pl_qty} &nbsp; | &nbsp;
        <b>Gross Weight:</b> {pl_gw}
      </div>
    </div>

    <div class="card">
      <div class="row"><div class="pill">Bill of Lading</div></div>
      <div class="muted">
        <b>BL #:</b> {bl_no} &nbsp; | &nbsp;
        <b>Gross Weight:</b> {bl_gw}
      </div>
    </div>
  </div>
  """

    html = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Pre-Filing Risk Report</title>
  <style>
    body {{ font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial; background:#0b1220; color:#e5e7eb; margin:0; }}
    .wrap {{ max-width: 980px; margin: 0 auto; padding: 28px 18px 60px; }}
    .top {{ display:flex; gap:14px; align-items:center; justify-content:space-between; flex-wrap:wrap; }}
    .title {{ font-size: 22px; font-weight: 700; }}
    .sub {{ color:#9ca3af; font-size: 13px; margin-top: 6px; }}
    .badge {{ background:{badge}; padding:10px 14px; border-radius: 999px; font-weight:800; letter-spacing: .6px; }}
    .grid {{ display:grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-top: 16px; }}
    .kpi {{ background:#111a2e; border:1px solid #24304e; border-radius:16px; padding:14px; }}
    .kpi .k {{ color:#9ca3af; font-size: 12px; }}
    .kpi .v {{ font-size: 18px; font-weight: 800; margin-top: 6px; }}
    .section {{ margin-top: 18px; }}
    .section .h2 {{ font-size: 16px; font-weight: 800; margin: 18px 0 10px; }}
    .card {{ background:#0f172a; border:1px solid #24304e; border-radius:16px; padding:14px; margin: 10px 0; }}
    .row {{ display:flex; gap:10px; align-items:center; flex-wrap:wrap; }}
    .pill {{ background:#1f2937; border:1px solid #334155; padding:4px 8px; border-radius:999px; font-size: 12px; font-weight: 800; }}
    .h3 {{ font-size: 14px; font-weight: 800; }}
    .muted {{ color:#cbd5e1; font-size: 13px; margin-top: 8px; line-height: 1.4; }}
    .rec {{ margin-top: 10px; padding-top: 10px; border-top: 1px solid #24304e; }}
    .h4 {{ font-size: 12px; font-weight: 900; color:#e5e7eb; margin-bottom: 6px; }}
    .back {{ 
      display: inline-block; 
      margin-bottom: 14px; 
      color: #93c5fd; 
      text-decoration: none; 
      font-weight: 700; 
        }}
    .back:hover {{ 
      text-decoration: underline; 
    }}
    .footer {{ margin-top: 22px; color:#94a3b8; font-size: 12px; }}
    a {{ color:#93c5fd; }}
  </style>
</head>
<body>
  <div class="wrap">
    <a class="back" href="/">← Back to home</a>
    <div class="top">
      <div>
        <div class="title">Pre-Filing Risk Report</div>
        <div class="sub">For brokers & exporters • Generated by Trade Doc AI MVP</div>
      </div>
      <div class="badge">{band.upper()}</div>
    </div>

    <div class="grid">
      <div class="kpi">
        <div class="k">Route</div>
        <div class="v">{route.get("origin_country","")} → {route.get("destination_country","")}</div>
      </div>
      <div class="kpi">
        <div class="k">Risk Score</div>
        <div class="v">{score}/100</div>
      </div>
      <div class="kpi">
        <div class="k">Action</div>
        <div class="v">Fix before filing</div>
      </div>
    </div>

    {summary_html}

    <div class="section">
      <div class="h2">Issues found</div>
      {issues_html}
    </div>

    <div class="footer">
      Tip: Align quantity/weight across Invoice, Packing List, and BL before filing to avoid holds & amendments.
    </div>
  </div>
</body>
</html>
"""
    return html

def html_response(report: Dict[str, Any]) -> HTMLResponse:
    return HTMLResponse(content=render_report_html(report))
