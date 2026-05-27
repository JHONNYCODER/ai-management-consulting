import math
import numpy as np
from analytics_pipeline.utils import sanitize_nan_values


def test_sanitize_nan_values_floats():
    """Ensures NaN and Inf floats are converted to None."""
    dirty_data = {
        "valid": 1.5,
        "nan_val": float("nan"),
        "inf_val": float("inf"),
        "neg_inf": float("-inf")
    }
    
    clean = sanitize_nan_values(dirty_data)
    
    assert clean["valid"] == 1.5
    assert clean["nan_val"] is None
    assert clean["inf_val"] is None
    assert clean["neg_inf"] is None


def test_sanitize_nan_values_numpy():
    """Ensures numpy integers and floats are converted to native Python types."""
    dirty_data = {
        "np_int": np.int64(42),
        "np_float": np.float64(3.14),
        "np_nan": np.float64("nan")
    }
    
    clean = sanitize_nan_values(dirty_data)
    
    assert isinstance(clean["np_int"], int)
    assert isinstance(clean["np_float"], float)
    assert clean["np_nan"] is None


def test_sanitize_nested_structures():
    """Ensures deeply nested lists/dicts are cleaned properly."""
    dirty_data = {
        "layer1": [
            {"val": float("nan"), "inner": [float("inf"), 10]}
        ]
    }
    
    clean = sanitize_nan_values(dirty_data)
    
    assert clean["layer1"][0]["val"] is None
    assert clean["layer1"][0]["inner"][0] is None
    assert clean["layer1"][0]["inner"][1] == 10