from typing import List, Literal
from .schemas import Issue

POINTS = {
    "critical": 30,
    "high": 15,
    "medium": 5,
    "low": 1,
}

def score_issues(issues: List[Issue]) -> int:
    return min(100, sum(POINTS[i.severity] for i in issues))

def risk_band(score: int) -> Literal["low", "medium", "high"]:
    if score <= 20:
        return "low"
    if score <= 50:
        return "medium"
    return "high"
