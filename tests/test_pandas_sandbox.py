"""Unit tests for Pandas sandbox security, AST restrictions, subprocess isolation, and timeout protection."""

import pandas as pd
import pytest
from app.tools.pandas_tool import (
    PandasSandboxError,
    execute_sandboxed_pandas,
    validate_pandas_code_safety,
)

@pytest.fixture
def sample_dfs():
    sales = pd.DataFrame({
        "order_id": ["ORD-1", "ORD-2", "ORD-3", "ORD-4"],
        "region": ["North", "South", "North", "West"],
        "revenue": [100.0, 200.0, 300.0, 400.0],
    })
    return {"sales": sales}

def test_valid_pandas_aggregation(sample_dfs):
    code = """
result = sales.groupby('region')['revenue'].sum().reset_index()
"""
    res = execute_sandboxed_pandas(code, sample_dfs, default_df_name="sales")
    assert isinstance(res, pd.DataFrame)
    assert len(res) == 3
    north_rev = res[res["region"] == "North"]["revenue"].iloc[0]
    assert north_rev == 400.0

def test_valid_pandas_scalar(sample_dfs):
    code = "result = sales['revenue'].mean()"
    res = execute_sandboxed_pandas(code, sample_dfs)
    assert isinstance(res, pd.DataFrame)
    assert res.iloc[0]["result"] == 250.0

def test_block_import_statements():
    with pytest.raises(PandasSandboxError, match="import statements are forbidden"):
        validate_pandas_code_safety("import os\nresult = df")

    with pytest.raises(PandasSandboxError, match="from ... import statements are forbidden"):
        validate_pandas_code_safety("from subprocess import check_output\nresult = df")

def test_block_pd_io_os_traversal():
    # Specifically tests pd.io.common.os.system
    with pytest.raises(PandasSandboxError, match="Access to attribute/method '(io|system)' is forbidden"):
        validate_pandas_code_safety('result = pd.io.common.os.system("echo hi")')

    with pytest.raises(PandasSandboxError, match="Access to attribute/method 'io' is forbidden"):
        validate_pandas_code_safety('result = pd.io')

def test_block_eval_and_query():
    with pytest.raises(PandasSandboxError, match="Access to attribute/method 'eval' is forbidden"):
        validate_pandas_code_safety("result = df.eval('revenue * 2')")

    with pytest.raises(PandasSandboxError, match="Access to attribute/method 'eval' is forbidden"):
        validate_pandas_code_safety("result = pd.eval('1 + 1')")

    with pytest.raises(PandasSandboxError, match="Access to attribute/method 'query' is forbidden"):
        validate_pandas_code_safety("result = df.query('revenue > 100')")

def test_block_numpy_io():
    with pytest.raises(PandasSandboxError, match="Access to attribute/method 'load' is forbidden"):
        validate_pandas_code_safety("result = np.load('data.npy')")

    with pytest.raises(PandasSandboxError, match="Access to attribute/method 'save' is forbidden"):
        validate_pandas_code_safety("result = np.save('data.npy', df)")

    with pytest.raises(PandasSandboxError, match="Access to attribute/method 'savetxt' is forbidden"):
        validate_pandas_code_safety("result = np.savetxt('data.txt', df)")

    with pytest.raises(PandasSandboxError, match="Access to attribute/method 'fromfile' is forbidden"):
        validate_pandas_code_safety("result = np.fromfile('data.bin')")

    with pytest.raises(PandasSandboxError, match="Access to attribute/method 'memmap' is forbidden"):
        validate_pandas_code_safety("result = np.memmap('data.bin')")

def test_block_dunder_names_and_attributes():
    with pytest.raises(PandasSandboxError, match="Access to dunder name '__builtins__' is forbidden"):
        validate_pandas_code_safety("result = __builtins__")

    with pytest.raises(PandasSandboxError, match="Access to dunder attribute '(__class__|__mro__)' is forbidden"):
        validate_pandas_code_safety("result = df.__class__.__mro__")

    with pytest.raises(PandasSandboxError, match="Access to dunder attribute '__class__' is forbidden"):
        validate_pandas_code_safety("result = df.__class__")

def test_block_forbidden_builtins():
    for fn in ["eval", "exec", "open", "getattr", "setattr", "compile"]:
        with pytest.raises(PandasSandboxError, match="is forbidden"):
            validate_pandas_code_safety(f"result = {fn}('something')")

def test_require_assignment_to_result():
    with pytest.raises(PandasSandboxError, match="must assign the final analytical output to a variable named 'result'"):
        validate_pandas_code_safety("x = df.head()")

def test_subprocess_timeout_on_infinite_loop(sample_dfs):
    code = """
while True:
    pass
result = sales
"""
    with pytest.raises(PandasSandboxError, match="timed out"):
        execute_sandboxed_pandas(code, sample_dfs, timeout_seconds=1)

def test_subprocess_huge_allocation_rejection(sample_dfs):
    code = """
# Attempt allocating 50 GB array
result = np.zeros((100000, 100000), dtype=np.float64)
"""
    with pytest.raises(PandasSandboxError):
        execute_sandboxed_pandas(code, sample_dfs, timeout_seconds=3)
