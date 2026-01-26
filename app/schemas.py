from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any

class Party(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    country: Optional[str] = None

class Item(BaseModel):
    description: Optional[str] = None
    hs_code: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    unit_value: Optional[float] = None
    gross_weight: Optional[float] = None
    net_weight: Optional[float] = None

class Issue(BaseModel):
    severity: Literal["critical", "high", "medium", "low"]
    code: str
    title: str
    explanation: str
    recommendation: str
    evidence: Dict[str, Any] = Field(default_factory=dict)

class Route(BaseModel):
    origin_country: Optional[str] = None
    destination_country: Optional[str] = None

class RiskReport(BaseModel):
    route: Route
    risk_score: int
    risk_band: Literal["low", "medium", "high"]
    issues: List[Issue]
    extracted_summary: Dict[str, Any]

    # 👇 NEW: optional debug payload
    debug: Optional[Dict[str, Any]] = Field(
    default=None,
    description="Internal extraction debug (not shown to end users)"
    )


    model_config = {
        "extra": "allow"
    }