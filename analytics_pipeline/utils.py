import math
import numpy as np
import pandas as pd

from analytics_pipeline.config import PipelineConfig

def safe_list(x):
    """Safely converts input to a list, handling None, single values, and iterables."""
    if x is None: 
        return []
    if isinstance(x, (list, tuple, set, np.ndarray, pd.Series)):
        return list(x)
    return [x]

def _clean_float(value, default=None):  # FIX: Default to None instead of 0.0
    try:
        fval = float(value)
        if math.isnan(fval) or math.isinf(fval): 
            return default
        return fval
    except (TypeError, ValueError): 
        return default

def classify_correlation_strength(value):
    v = abs(_clean_float(value, 0.0)) # Fallback to 0.0 for classification purposes
    if v < 0.2: return "negligible"
    elif v < 0.4: return "weak"
    elif v < 0.6: return "moderate"
    elif v < 0.8: return "strong"
    return "very strong"

def map_priority_from_score(score):
    score = _clean_float(score, 0.0)
    if score >= 0.75: return "high"
    elif score >= 0.45: return "medium"
    return "low"

def is_identifier_column(col_name, series):
    if not col_name: return False
    name = col_name.lower().replace("_", "").replace(" ", "")
    
    if any(kw in name for kw in ["id", "uuid", "employeeid", "userid", "customerid", "serial", "code"]):
        return True
    
    if not pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_string_dtype(series): 
        return False
    
    clean = series.dropna()
    if len(clean) < 3: return False
    
    unique_ratio = clean.nunique() / len(clean)
    
    if unique_ratio > 0.95:
        try:
            if clean.is_monotonic_increasing or clean.is_monotonic_decreasing:
                return True
        except Exception:
            pass
        
        if pd.api.types.is_string_dtype(series) and clean.nunique() == len(clean):
            return True
            
    return False

def _assign_tags(col_name, config: PipelineConfig):
    name = col_name.lower().replace("_", "").replace(" ", "")
    tags = [tag for tag, keywords in config.tag_keywords.items() if any(kw in name for kw in keywords)]
    return tags if tags else ["general"]

def _derive_theme_name(variables_list, taxonomy):
    all_tags = set()
    for v in variables_list: 
        all_tags.update(taxonomy.get(v, ["general"]))
        
    if "compensation" in all_tags: return "Compensation and progression cluster"
    elif "experience" in all_tags: return "Experience and tenure cluster"
    elif "performance" in all_tags: return "Performance and score cluster"
    elif "satisfaction" in all_tags: return "Satisfaction and engagement cluster"
    
    if len(variables_list) >= 2: return f"{variables_list[0]} vs {variables_list[1]}"
    elif variables_list: return variables_list[0]
    return "General patterns cluster"

def sanitize_nan_values(obj):
    """
    Recursively cleans a dictionary/list so it is JSON/Pydantic safe.
    Converts NaN/Inf to None, and numpy types to native Python types.
    """
    if isinstance(obj, dict): 
        return {k: sanitize_nan_values(v) for k, v in obj.items()}
    elif isinstance(obj, list): 
        return [sanitize_nan_values(v) for v in obj]
    elif isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)): 
        return None
    elif isinstance(obj, (np.integer,)): 
        return int(obj)
    elif isinstance(obj, (np.floating,)): 
        return float(obj)
    return obj