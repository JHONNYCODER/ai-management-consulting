# ─────────────────────────────────────────────
# LAYER 5: DECISION
# ─────────────────────────────────────────────

import uuid

def generate_executive_synthesis(state):
    config = state["config"]
    ct = state.get("cross_theme_reasoning") or {}
    stab = state.get("analytical_stability") or {}
    raw = state.get("raw_signals") or []
    
    dom = ct.get("dominant_themes", [])
    cp = float(ct.get("conflict_pressure", 0)) # Already 0-1 from reasoning layer!
    shs = float(stab.get("system_health_score", 50))
    scs = float(stab.get("signal_confidence_score", 0.5))
    sl = stab.get("label", "unknown")
    
    shs_n = max(0.0, min(1.0, shs / 100.0))

    key_drivers, key_drivers_meta = [], []
    for t in dom[:config.max_dominant_themes]:
        if not isinstance(t, dict) or not t.get("theme"): continue
        bundle = t.get("signal_strength_bundle", {})
        if bundle.get("signal_count", 0) <= 0 or bundle.get("normalized_strength", 0) < 0.15: continue
        key_drivers.append(t["theme"])
        key_drivers_meta.append({
            "name": t["theme"], 
            "signal_strength_bundle": bundle, 
            "variables": t.get("variables", []), 
            "driver_id": str(uuid.uuid4())
        })
        
    risks, opps = [], []
    if shs < 60: risks.append("Low analytical stability")
    if cp > 0.3: risks.append("Structural overlap between themes")  # noqa: E701
    if not dom: risks.append("No dominant structural themes")
    for t in dom[:3]:
        if isinstance(t, dict):
            avg = t.get("signal_strength_bundle", {}).get("avg_strength", 0)
            if avg > 0.4: opps.append(f"Structural relationship observed in {t.get('theme')} (avg: {avg:.2f})")
    
    df = (
        "Dataset shows reliable structural patterns"
        if shs_n > 0.75 and opps
        else "Moderate reliability"
        if shs_n > 0.5
        else "Unstable patterns; exploratory only"
    )
    drivers_text = ", ".join(key_drivers) if key_drivers else "None identified"
    summary = f"Primary drivers: {drivers_text}."

    iconfs = [float(i.get("confidence", 0.5)) for i in raw if isinstance(i, dict)]
    ic = sum(iconfs) / len(iconfs) if iconfs else 0.5
    
    ic_n = max(0.0, min(1.0, ic))              
    scs_n = max(0.0, min(1.0, scs))
    cp_n = max(0.0, min(1.0, cp)) # FIX: Removed / 15.0 so penalty actually works!
    
    stability = max(0.0, min(1.0, stab.get("stability_index", 60) / 100.0))
    signal_conf = scs_n
    conflict_penalty = cp_n

    fc = (
        0.5 * signal_conf +
        0.3 * stability +
        0.2 * (1 - conflict_penalty)
    )

    fc = max(0.05, min(0.99, fc))

    state["executive_synthesis"] = {
        "executive_summary": summary.strip(), 
        "decision_frame": df, 
        "key_drivers": key_drivers, 
        "key_drivers_meta": key_drivers_meta, 
        "risk_signals": risks, 
        "opportunity_signals": opps, 
        "confidence": round(fc, 3), 
        "score": round(fc * 100, 2), 
        "stability_label": sl
    }
    
    return state

def generate_structured_reasoning(state):
    raw = state.get("raw_signals") or []
    tm = state.get("theme_metrics", {}) or {}
    exec_s = state.get("executive_synthesis", {}) or {}
    sys_conf = float(exec_s.get("confidence", 0.5))
    
    findings = [
        {"finding": i.get("pair", ""), "evidence": {"pearson": i.get("pearson"), "strength": i.get("strength"), "significance": i.get("significance")}, "confidence": sys_conf, "priority": i.get("priority", "low")} 
        for i in raw[:5] if isinstance(i, dict)
    ]
    patterns = [
        {"pattern": t.get("theme", ""), "variables": t.get("variables", []), "signal_count": t.get("signal_strength_bundle", {}).get("signal_count", 0), "avg_strength": t.get("signal_strength_bundle", {}).get("avg_strength", 0)} 
        for t in tm.get("themes", [])[:5] if isinstance(t, dict)
    ]
    warnings = [{"warning": r, "severity": "medium", "type": "executive_risk"} for r in exec_s.get("risk_signals", [])]
    
    state["structured_reasoning"] = {"findings": findings, "patterns": patterns, "warnings": warnings, "gaps": []}
    return state