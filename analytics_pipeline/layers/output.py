# ─────────────────────────────────────────────
# LAYER 6: OUTPUT
# ─────────────────────────────────────────────

def generate_narrative_summary(state):
    exec_s = state.get("executive_synthesis", {}) or {}
    stab = state.get("analytical_stability", {}) or {}
    health = state.get("dataset_health", {}) or {}
    hs, si = health.get("health_score", 0), stab.get("stability_index", 0)
    kd, sl = exec_s.get("key_drivers", []), exec_s.get("stability_label", "unknown")
    state["narrative_summary"] = {"full_narrative": f"Dataset quality score is {hs}/100. Primary drivers: {', '.join(kd)}. Stability is {sl} (index: {si})."}
    return state

def generate_final_insights(state):
    exec_s = state.get("executive_synthesis", {}) or {}
    state["final_insights"] = {"key_findings": exec_s.get("key_drivers", []), "supporting_evidence": exec_s.get("opportunity_signals", []), "warnings": exec_s.get("risk_signals", []), "summary": exec_s.get("executive_summary", "")}
    return state

def align_contradictions(state): 
    # Logic preserved for future implementation
    return state 

# This generates Narratives
def generate_recommendations(state):
    config = state["config"]
    exec_s = state.get("executive_synthesis", {}) or {}
    taxonomy = state.get("signal_taxonomy", {}) or {}
    correlations = state.get("correlations", {}).get("pairs", [])
    recs = []
    sys_conf = float(exec_s.get("confidence", 0.3))
    
    # 1. Try generating from key drivers
    for dm in exec_s.get("key_drivers_meta", []):
        if not isinstance(dm, dict): continue
        bundle = dm.get("signal_strength_bundle", {})
        vars_list = dm.get("variables", [])
        avg = float(bundle.get("avg_strength", 0))
        if avg < 0.2: continue # Lowered threshold to catch more
        
        pri = "high" if avg > 0.6 else "medium"
        clean_vars = ", ".join(vars_list[:3]) if vars_list else "these factors"
        
        tags = set(t for v in vars_list for t in taxonomy.get(v, ["general"]))
        priority_order = ["compensation", "performance", "experience", "satisfaction", "demographic", "education", "attendance"]
        ordered_tags = [t for t in priority_order if t in tags] + [t for t in tags if t not in priority_order]
        primary_tag = ordered_tags[0] if ordered_tags else "general"
        
        if primary_tag != "general":
            action = f"Review your {primary_tag} strategy"
            reason = f"The data shows that {clean_vars} are strongly connected. Improving your {primary_tag} approach could have a big impact."
        else:
            action = f"Take a closer look at {clean_vars}"
            reason = f"These factors are moving together. Figuring out why could reveal a hidden opportunity."
            
        recs.append({"action": action, "reason": reason, "priority": pri, "confidence": round(sys_conf, 3), "driver_id": dm.get("driver_id")})
    
    # 2. Fallback: If we have less than 3, generate from top correlations!
    if len(recs) < 3 and correlations:
        for pair in correlations[:3]:
            pair_name = pair.get("pair", "")
            strength = pair.get("strength", "weak")
            if strength in ["strong", "very strong", "moderate"] and " vs " in pair_name:
                v1, v2 = pair_name.split(" vs ")[0].strip(), pair_name.split(" vs ")[1].strip()
                recs.append({
                    "action": f"Analyze the relationship between {v1} and {v2}",
                    "reason": f"These two metrics have a {strength} correlation. Adjusting one will likely affect the other.",
                    "priority": "high" if strength in ["strong", "very strong"] else "medium",
                    "confidence": round(sys_conf, 3),
                    "driver_id": None
                })
            if len(recs) >= 3: break

    # 3. Absolute Fallback (if data is just completely empty)
    if not recs:
        recs.append({
            "action": "Collect more data",
            "reason": "Current data lacks strong patterns. A larger dataset will help uncover hidden insights.",
            "priority": "medium",
            "confidence": round(sys_conf, 3),
            "driver_id": None
        })

    state["recommendations"] = {"recommendations": recs, "total_recommendations": len(recs), "system_confidence": round(sys_conf, 3)}
    return state