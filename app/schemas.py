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

class RiskReport(BaseModel):
    route: Dict[str, str]
    risk_score: int
    risk_band: Literal["low", "medium", "high"]
    issues: List[Issue]
    extracted_summary: Dict[str, Any]
