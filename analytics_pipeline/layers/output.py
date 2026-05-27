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

def generate_recommendations(state):
    config = state["config"]
    exec_s = state.get("executive_synthesis", {}) or {}
    taxonomy = state.get("signal_taxonomy", {}) or {}
    recs = []
    sys_conf = float(exec_s.get("confidence", 0.3))
    
    for dm in exec_s.get("key_drivers_meta", []):
        if not isinstance(dm, dict): continue
        bundle = dm.get("signal_strength_bundle", {})
        vars_list = dm.get("variables", []) # FIX: Renamed 'vars' to 'vars_list'
        avg = float(bundle.get("avg_strength", 0))
        if avg < 0.3: continue
        
        pri = "high" if avg > 0.6 else "medium"
        tags = set(t for v in vars_list for t in taxonomy.get(v, ["general"]))
        action_found = False
        
        # Define priority order for recommendations
        priority_order = ["compensation", "performance", "experience", "satisfaction", "demographic", "education", "attendance"]
        ordered_tags = [t for t in priority_order if t in tags] + [t for t in tags if t not in priority_order]
        
        for tag in ordered_tags:
            if tag in config.tag_action_map and tag != "general":
                recs.append({"action": config.tag_action_map[tag]["action"], "reason": f"Cluster '{dm.get('name')}' avg: {avg:.2f}", "priority": pri, "confidence": round(sys_conf, 3), "driver_id": dm.get("driver_id")})
                action_found = True
                break
                
        if not action_found: 
            fallback_vars = ", ".join(vars_list[:3]) if vars_list else "this pattern"
            recs.append({"action": f"Investigate {fallback_vars}", "reason": f"Cluster '{dm.get('name')}' avg: {avg:.2f}", "priority": pri, "confidence": round(sys_conf, 3), "driver_id": dm.get("driver_id")})
    
    state["recommendations"] = {"recommendations": recs, "total_recommendations": len(recs), "system_confidence": round(sys_conf, 3)}
    return state