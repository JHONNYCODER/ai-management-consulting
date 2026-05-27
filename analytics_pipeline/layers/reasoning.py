# ─────────────────────────────────────────────
# LAYER 4: REASONING ASSEMBLY
# ─────────────────────────────────────────────

import math
from typing import Dict
from collections import defaultdict

from analytics_pipeline.utils import safe_list
from analytics_pipeline.logger import logger

def generate_derived_signals(state):
    derived = []

    for item in state.get("raw_signals") or []:
        if not isinstance(item, dict):
            continue

        pair = item.get("pair", "")
        ss = item.get("strength", "weak")
        sig = item.get("significance", "")

        pv = float(item.get("pearson") or 0)
        score = float(item.get("score") or 0)
        conf = float(item.get("confidence") or 0.5)

        d = "positive" if pv > 0 else "negative" if pv < 0 else "neutral"

        if ss in ["strong", "very strong"]:
            msg = f"{pair} demonstrates a strong {d} statistical relationship"
        elif ss == "moderate":
            msg = f"{pair} shows a moderate {d} statistical relationship"
        else:
            msg = f"{pair} shows little to no {d} statistical relationship"

        if sig == "not significant":
            msg += ", though evidence is limited"
        elif sig == "highly significant":
            msg += " with highly reliable evidence"

        c = float(conf or 0.5)
        confidence_label = (
            "very high" if c >= 0.85 else
            "high" if c >= 0.7 else
            "moderate" if c >= 0.55 else
            "low"
        )

        derived.append({
            "pair": pair,
            "message": msg,
            "confidence_label": confidence_label,
            "justification": {
                "base_signal": f"signal strength {score}",
                "boosts": ["strong statistical signal"] if score > 0.7 else [],
                "penalties": [],
                "final_reason": "Strong and reliable signal" if c >= 0.7 else "Moderate signal requiring context"
            }
        })

    state["derived_signal_view"] = derived
    return state

def generate_analytical_stability(state):
    health = state.get("dataset_health") or {}
    raw = state.get("raw_signals") or []
    conflicts = state.get("conflicts") or []
    
    hs = float(health.get("health_score", 50))
    ac = int(health.get("anomaly_count", 0))
    n = int(state.get("rows", 0))
    
    # 1. Health Normalization (0 to 1)
    health_norm = max(0, min(100, hs)) / 100.0
    
    # 2. Signal Confidence (0 to 1)
    confs = [float(i.get("confidence", 0.5)) for i in raw if isinstance(i, dict)]
    signal_conf = round(sum(confs) / len(confs), 3) if confs else 0.5
    
    # 3. Dataset Size Score (Fairer curve)
    size_score = min(1.0, (math.log10(n + 1) / 2.0)) # n=8 -> 0.47, n=100 -> 1.0
    
    # 4. Penalties
    anomaly_penalty = min(1.0, (ac / max(n, 1)))
    
    conflict_score = sum(
        8.0 if c.get("severity") == "high" else 4.0 if c.get("severity") == "medium" else 1.5 
        for c in conflicts
    )
    conflict_penalty = min(1.0, conflict_score / 15.0)
    
    # 5. Final Stability Calculation
    base_stability = (0.40 * health_norm) + (0.30 * signal_conf) + (0.30 * size_score)
    
    # Apply penalties (reduced harshness)
    penalized_stability = base_stability * (1 - 0.15 * conflict_penalty) * (1 - 0.3 * anomaly_penalty)
    
    # ✅ QUALITY BOOST: If data is clean and signals are strong, boost it!
    top_pearson = max([abs(float(i.get("pearson", 0))) for i in raw if isinstance(i, dict)], default=0)
    if health_norm >= 0.9 and top_pearson >= 0.8:
        penalized_stability += 0.15  # Reward perfect health + strong correlations
    
    stability_index = round(max(0, min(100, penalized_stability * 100)), 1)

    state["analytical_stability"] = {
        "system_health_score": round(health_norm * 100, 1),
        "signal_confidence_score": signal_conf,
        "stability_index": stability_index,
        "label": (
            "high" if stability_index >= 80 else
            "moderate" if stability_index >= 60 else
            "guarded" if stability_index >= 40 else 
            "low"
        ),
        "normalization": {
            "health_norm": health_norm,
            "size_score": size_score,
            "anomaly_penalty": anomaly_penalty,
            "conflict_penalty": conflict_penalty
        },
        "summary": f"stability={stability_index}"
    }

    return state

def generate_cross_theme_reasoning(state):
    tm = state.get("theme_metrics", {})
    tb = tm.get("themes", [])
    dom = tm.get("dominant_themes", [])
    ss = tm.get("structural_strength", 0)
    
    if not tb: 
        state["cross_theme_reasoning"] = {
            "dominant_themes": [], "theme_interactions": [], 
            "conflict_pressure": 0, "structural_strength": 0
        }
        return state
    
    interactions = []
    for i in range(len(tb)):
        for j in range(i + 1, len(tb)):
            vars_i = safe_list(tb[i].get("variables", []))
            vars_j = safe_list(tb[j].get("variables", []))
            overlap = len(set(vars_i).intersection(set(vars_j)))
            
            interactions.append({
                "theme_a": tb[i].get("theme", "Unknown"), 
                "theme_b": tb[j].get("theme", "Unknown"), 
                "interaction": "reinforcing" if overlap > 0 else "independent", 
                "overlap_score": overlap
            })
    
    conflicts = state.get("conflicts") or []
    cp = round(min(len(conflicts) / (len(tb) + 1), 1.0), 3)
    
    state["cross_theme_reasoning"] = {
        "dominant_themes": dom, 
        "theme_interactions": interactions, 
        "conflict_pressure": cp, 
        "structural_strength": ss
    }
    return state