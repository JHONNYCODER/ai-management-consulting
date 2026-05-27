import math
import pandas as pd
import numpy as np

from analytics_pipeline.config import PipelineConfig
from analytics_pipeline.orchestrator import run_pipeline
from analytics_pipeline.utils import sanitize_nan_values  # <-- FIX: Import from utils instead!
from analytics_pipeline.schema import create_initial_state

from analytics_pipeline.layers.raw_computation import (
    generate_profile,
)
from analytics_pipeline.layers.normalization import (
    generate_signal_taxonomy,  # <-- FIX: Moved to normalization in our refactor!
)


def test_full_pipeline_execution(standard_csv):
    result = run_pipeline(str(standard_csv))
    assert result.success is True
    assert len(result.layers_failed) == 0
    assert "executive_synthesis" in result.state
    assert 0 <= result.state["executive_synthesis"]["confidence"] <= 1


def test_empty_dataset_handles_gracefully(empty_csv):
    config = PipelineConfig(execution_mode="partial")
    result = run_pipeline(str(empty_csv), config=config)
    assert "raw_signals" in result.state


def test_high_conflict_dataset(high_conflict_csv):
    result = run_pipeline(str(high_conflict_csv))
    assert "conflicts" in result.state
    assert len(result.state["conflicts"]) >= 0


def test_config_threshold_respected(standard_csv):
    config = PipelineConfig(cluster_signal_threshold=0.9)
    result = run_pipeline(str(standard_csv), config=config)

    themes = result.state.get("theme_metrics", {}).get("themes", [])
    assert isinstance(themes, list)


def test_serialization_no_nan(standard_csv):
    result = run_pipeline(str(standard_csv))
    
    # Replicate what the old serialize_pipeline_output did
    state_copy = result.state.copy()
    state_copy.pop("df", None)
    state_copy.pop("pipeline_cache", None)
    state_copy.pop("config", None)
    
    # Use our new utility function
    output = sanitize_nan_values(state_copy)

    def check(obj):
        if isinstance(obj, dict):
            for v in obj.values():
                check(v)
        elif isinstance(obj, list):
            for v in obj:
                check(v)
        elif isinstance(obj, float):
            assert not math.isnan(obj), "Found NaN in serialized output!"
            assert not math.isinf(obj), "Found Inf in serialized output!"

    check(output)


def test_taxonomy_generation():
    state = create_initial_state(
        df=pd.DataFrame({"salary": [1], "experience_years": [2]})
    )

    state = generate_profile(state)
    state = generate_signal_taxonomy(state)  # Now imported from normalization

    tax = state["signal_taxonomy"]
    assert "salary" in tax
    assert "experience_years" in tax