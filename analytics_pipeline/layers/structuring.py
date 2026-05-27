# ─────────────────────────────────────────────
# LAYER 3: STRUCTURING
# ─────────────────────────────────────────────

from collections import defaultdict

from analytics_pipeline.utils import _derive_theme_name
from analytics_pipeline.logger import logger 


def generate_contextual_synthesis(state):
    config = state["config"]
    raw = state.get("raw_signals") or []
    taxonomy = state.get("signal_taxonomy", {})
    var_map = defaultdict(list)
    
    for item in raw:
        if not isinstance(item, dict): continue
        pair = item.get("pair", "")
        if " vs " not in pair: continue
        
        # Added maxsplit=1 in case column names contain " vs "
        try:
            v1, v2 = pair.split(" vs ", 1)
            v1, v2 = v1.strip(), v2.strip()
        except ValueError:
            logger.warning(f"Malformed pair skipped: {pair}", extra={"layer": "structuring"})
            continue
            
        entry = {"type": "correlation", "strength": item.get("strength", ""), "value": item.get("pearson", 0), "pair": pair}
        var_map[v1].append({"related_to": v2, **entry})
        var_map[v2].append({"related_to": v1, **entry})
    
    themes, used = [], set()
    for var, rels in var_map.items():
        if var in used: continue
        cluster_vars, signals = {var}, []
        for r in rels:
            if abs(r.get("value", 0)) >= config.cluster_signal_threshold:
                cluster_vars.add(r["related_to"])
                signals.append(r)
        used.update(cluster_vars)
        
        if not signals: 
            themes.append({"theme": var, "variables": [var], "supporting_signals": []})
            continue
            
        conn = {v: sum(abs(r.get("value", 0)) for r in var_map.get(v, []) if abs(r.get("value", 0)) >= config.cluster_signal_threshold) for v in cluster_vars}
        v_list = sorted(conn, key=conn.get, reverse=True)
        themes.append({"theme": _derive_theme_name(v_list, taxonomy), "variables": v_list, "supporting_signals": signals})
    
    state["contextual_synthesis"] = {
        "themes": themes, 
        "cross_variable_patterns": [
            {"pattern": "multi-variable", "theme": t["theme"], "variables": t["variables"]} 
            for t in themes if len(t["variables"]) >= 3 and t["supporting_signals"]
        ]
    }
    return state


def generate_theme_metrics(state):
    themes = (state.get("contextual_synthesis") or {}).get("themes", [])
    bundles, all_str = [], []
    for t in themes:
        sigs = t.get("supporting_signals", [])
        str_vals = [abs(s.get("value", 0)) for s in sigs if isinstance(s, dict)]
        avg = round(sum(str_vals) / len(str_vals), 3) if str_vals else 0
        bundle = {"avg_strength": avg, "signal_count": len(sigs), "max_strength": round(max(str_vals), 3) if str_vals else 0, "normalized_strength": avg}
        bundles.append({"theme": t.get("theme", ""), "variables": t.get("variables", []), "signal_strength_bundle": bundle})
        all_str.extend(str_vals)
    
    sorted_b = sorted(bundles, key=lambda x: x["signal_strength_bundle"]["avg_strength"], reverse=True)
    dominant = sorted_b[:3]
    struct_str = round(sum(t["signal_strength_bundle"]["avg_strength"] for t in dominant) / len(dominant), 3) if dominant else 0
    overall = {"avg_strength": round(sum(all_str) / len(all_str), 3) if all_str else 0, "signal_count": len(all_str), "max_strength": round(max(all_str), 3) if all_str else 0, "normalized_strength": round(sum(all_str) / len(all_str), 3) if all_str else 0}
    
    state["theme_metrics"] = {"themes": bundles, "dominant_themes": dominant, "structural_strength": struct_str, "overall_strength_bundle": overall}
    return state