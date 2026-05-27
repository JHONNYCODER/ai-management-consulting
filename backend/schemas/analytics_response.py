from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class Summary(BaseModel):
    rows: int
    columns: int


class ProfileMetric(BaseModel):
    type: str
    mean: Optional[float] = None
    median: Optional[float] = None
    std: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    unique_values: Optional[int] = None
    top_value: Optional[str] = None


class CorrelationPair(BaseModel):
    pair: str
    pearson: float
    strength: str
    p_value: float
    significance: str


class DatasetHealth(BaseModel):
    completeness_score: float
    anomaly_count: int
    dominance_issues: int
    health_score: float


class ExecutiveSynthesis(BaseModel):
    executive_summary: str
    decision_frame: str
    key_drivers: List[str]
    confidence: float = Field(ge=0.0, le=1.0)
    score: float = Field(ge=0.0, le=100.0)    # <--- FIXED: Allow 0-100
    stability_label: str

class AnalyticsResponseData(BaseModel):
    file_name: str
    summary: Summary
    profile: Dict[str, ProfileMetric]
    correlations: Dict[str, List[CorrelationPair]]
    anomaly_details: List[Dict[str, Any]]
    dataset_health: DatasetHealth
    analytical_stability: Dict[str, Any]
    conflicts: List[Dict[str, Any]]
    contextual_synthesis: Dict[str, Any]
    cross_theme_reasoning: Dict[str, Any]
    narrative_summary: Dict[str, Any]
    final_insights: Dict[str, Any]
    executive_synthesis: ExecutiveSynthesis
    recommendations: Dict[str, Any]
    chart_url: Optional[str]
    chart_path: Optional[str]
    chart_data: Optional[Dict[str, Any]] = None

class AnalyticsResponse(BaseModel):
    status: str
    data: AnalyticsResponseData