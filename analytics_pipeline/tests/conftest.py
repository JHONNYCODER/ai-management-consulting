import pytest
import pandas as pd
import numpy as np


@pytest.fixture
def standard_csv(tmp_path):
    df = pd.DataFrame({
        "salary": np.random.normal(60000, 15000, 100),
        "experience_years": np.random.randint(1, 20, 100),
        "performance_score": np.random.uniform(1, 5, 100),
        "id": range(100)
    })
    path = tmp_path / "data.csv"
    df.to_csv(path, index=False)
    return path


@pytest.fixture
def empty_csv(tmp_path):
    df = pd.DataFrame({"col1": [], "col2": []})
    path = tmp_path / "empty.csv"
    df.to_csv(path, index=False)
    return path


@pytest.fixture
def high_conflict_csv(tmp_path):
    df = pd.DataFrame({
        "a": np.random.normal(0, 1, 10),
        "b": np.random.normal(0, 1, 10)
    })
    path = tmp_path / "conflict.csv"
    df.to_csv(path, index=False)
    return path