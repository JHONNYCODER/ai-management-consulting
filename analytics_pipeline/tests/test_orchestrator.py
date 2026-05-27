import pytest
import pandas as pd
import tempfile
import os

from analytics_pipeline.orchestrator import (
    PIPELINE_REGISTRY, 
    run_pipeline, 
    execute_pipeline_layer,
    PipelineExecutionResult
)
from analytics_pipeline.config import PipelineConfig
from analytics_pipeline.schema import create_initial_state


def test_registry_order():
    """
    Ensures that layers depending on other layers run in the correct order.
    Specifically, executive_synthesis MUST run before structured_reasoning.
    """
    names = [layer["name"] for layer in PIPELINE_REGISTRY]
    
    exec_idx = names.index("executive_synthesis")
    struct_idx = names.index("structured_reasoning")
    
    assert exec_idx < struct_idx, (
        "executive_synthesis must run before structured_reasoning in the registry!"
    )


def test_run_pipeline_with_mock_csv():
    """
    Tests a full pipeline run with a tiny, valid CSV.
    """
    # Create a temporary CSV file
    df = pd.DataFrame({
        "col_a": [1, 2, 3, 4, 5],
        "col_b": [5, 4, 3, 2, 1], # Perfect negative correlation
        "col_c": ["x", "y", "z", "x", "y"] # Categorical
    })
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        df.to_csv(f, index=False)
        temp_path = f.name

    try:
        config = PipelineConfig(execution_mode="fail_fast")
        result = run_pipeline(temp_path, config=config)
        
        # Assertions
        assert isinstance(result, PipelineExecutionResult)
        assert result.success is True
        assert len(result.layers_failed) == 0
        assert "executive_synthesis" in result.state
        assert "analytical_stability" in result.state
        assert isinstance(result.state["raw_signals"], list)
        
    finally:
        os.remove(temp_path)


def test_execute_layer_missing_dependency():
    """
    Tests that a layer fails gracefully if its required inputs are missing.
    """
    config = PipelineConfig(execution_mode="fail_fast")
    state = create_initial_state(df=pd.DataFrame(), config=config)
    
    # We are going to try running 'contextual_synthesis' without 'raw_signals'
    fake_layer = {
        "name": "contextual_synthesis",
        "fn": lambda s: s,
        "requires": ["raw_signals", "signal_taxonomy"] # raw_signals is empty []
    }
    
    # Remove raw_signals to force a failure
    state.pop("raw_signals", None)
    
    with pytest.raises(Exception): # Should raise a ValidationError/PipelineError
        execute_pipeline_layer(state, fake_layer, config)