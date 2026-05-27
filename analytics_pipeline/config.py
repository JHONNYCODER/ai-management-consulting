from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

@dataclass
class PipelineConfig:
    cluster_signal_threshold: float = 0.25
    weak_signal_filter: float = 0.10
    output_dir: Optional[str] = None  

    # Enforce valid strings using Literal
    confidence_scale: Literal["0_1", "-1_1"] = "0_1"
    signal_range: Literal["-1_to_1", "0_1"] = "-1_to_1"
    stability_range: Literal["0_100"] = "0_100"
    health_range: Literal["0_100"] = "0_100"
    
    insight_sensitivity: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
        "correlation": {"dataset_size_weight": 0.6, "conflict_penalty_weight": 0.7, "health_weight": 0.9},
        "health": {"dataset_size_weight": 0.3, "conflict_penalty_weight": 0.2, "health_weight": 1.0},
        "variability": {"dataset_size_weight": 0.8, "conflict_penalty_weight": 0.5, "health_weight": 0.6},
    })
    
    tag_keywords: Dict[str, List[str]] = field(default_factory=lambda: {
        "compensation": ["salary", "compensation", "wage", "pay", "income", "bonus", "remuneration"],
        "experience": ["experience", "tenure", "years", "seniority", "service"],
        "performance": ["performance", "score", "rating", "evaluation", "assessment", "kpi"],
        "demographic": ["age", "gender", "ethnicity", "race", "nationality", "location", "region", "department", "team"],
        "temporal": ["date", "time", "year", "month", "quarter", "period", "fiscal"],
        "satisfaction": ["satisfaction", "engagement", "happiness", "survey", "feedback", "nps"],
        "education": ["education", "degree", "qualification", "certification", "diploma"],
        "attendance": ["attendance", "absence", "leave", "absenteeism", "presence"],
    })
    
    tag_action_map: Dict[str, Dict[str, str]] = field(default_factory=lambda: {
        "compensation": {"action": "Review compensation alignment with performance and experience metrics"},
        "experience": {"action": "Optimize hiring and promotion policies based on experience impact"},
        "performance": {"action": "Re-evaluate performance scoring linkage with compensation models"},
        "demographic": {"action": "Analyze demographic distribution for equity and representation patterns"},
        "satisfaction": {"action": "Investigate satisfaction drivers and their relationship to retention"},
        "education": {"action": "Evaluate education-credential impact on outcomes"},
        "attendance": {"action": "Review attendance patterns and their impact on performance"},
        "temporal": {"action": "Examine temporal trends for seasonal or cyclical patterns"},
    })

    significance_scores: Dict[str, float] = field(default_factory=lambda: {
        "highly significant": 0.9, "significant": 0.75, "moderate": 0.55, 
        "weak": 0.35, "not significant": 0.2
    })
    
    strength_bonuses: Dict[str, float] = field(default_factory=lambda: {
        "negligible": 0.85, "weak": 0.92, "moderate": 1.0, "strong": 1.08, "very strong": 1.15
    })
    
    max_raw_signals: int = 10
    max_dominant_themes: int = 3
    
    # Enforced execution modes
    execution_mode: Literal["fail_fast", "partial", "debug"] = "fail_fast"