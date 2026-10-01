"""Sandboxed Pandas and NumPy Python code execution environment with subprocess isolation."""

import ast
from pathlib import Path
import pickle
import subprocess
import sys
import tempfile
from typing import Any, Dict, Optional
import numpy as np
import pandas as pd

from app.utils.logging import get_logger

logger = get_logger()

class PandasSandboxError(Exception):
    """Raised when Python code violates sandbox constraints."""
    pass

FORBIDDEN_CALLS = {
    "eval",
    "exec",
    "compile",
    "open",
    "getattr",
    "setattr",
    "delattr",
    "globals",
    "locals",
    "vars",
    "__import__",
    "breakpoint",
    "exit",
    "quit",
    "input",
    "help",
}

# Block dangerous submodules and methods on libraries
FORBIDDEN_ATTRIBUTES = {
    "io",
    "os",
    "sys",
    "compat",
    "util",
    "testing",
    "core",
    "api",
    "system",
    "subprocess",
    "popen",
    "spawn",
    "eval",
    "query",
    "load",
    "save",
    "savetxt",
    "fromfile",
    "memmap",
    "tofile",
}

SAFE_BUILTINS: Dict[str, Any] = {
    "abs": abs,
    "all": all,
    "any": any,
    "bin": bin,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "format": format,
    "frozenset": frozenset,
    "int": int,
    "isinstance": isinstance,
    "issubclass": issubclass,
    "iter": iter,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "next": next,
    "print": lambda *args, **kwargs: None,
    "range": range,
    "reversed": reversed,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
    "True": True,
    "False": False,
    "None": None,
}

class SandboxSecurityVisitor(ast.NodeVisitor):
    """AST visitor enforcing strict sandbox safety constraints."""

    def __init__(self):
        self.assigns_to_result = False

    def visit_Import(self, node: ast.Import):
        raise PandasSandboxError("import statements are forbidden in sandboxed execution.")

    def visit_ImportFrom(self, node: ast.ImportFrom):
        raise PandasSandboxError("from ... import statements are forbidden in sandboxed execution.")

    def visit_Attribute(self, node: ast.Attribute):
        attr = node.attr
        # Block dunder attribute access
        if attr.startswith("__"):
            raise PandasSandboxError(f"Access to dunder attribute '{attr}' is forbidden.")

        # Block dangerous module attributes, eval, and I/O methods
        if attr in FORBIDDEN_ATTRIBUTES:
            raise PandasSandboxError(f"Access to attribute/method '{attr}' is forbidden.")

        # Block file-read and export methods
        if attr.startswith("read_"):
            raise PandasSandboxError(f"Calling file-reading method '{attr}' is forbidden.")
        if attr.startswith("to_"):
            raise PandasSandboxError(f"Calling export method '{attr}' is forbidden.")

        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        name = node.id
        if name in FORBIDDEN_CALLS:
            raise PandasSandboxError(f"Use of built-in function '{name}' is forbidden.")
        # Block dunder identifiers (e.g. __builtins__)
        if name.startswith("__"):
            raise PandasSandboxError(f"Access to dunder name '{name}' is forbidden.")
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "result":
                self.assigns_to_result = True
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign):
        if isinstance(node.target, ast.Name) and node.target.id == "result":
            self.assigns_to_result = True
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        if isinstance(node.target, ast.Name) and node.target.id == "result":
            self.assigns_to_result = True
        self.generic_visit(node)

def validate_pandas_code_safety(code: str) -> None:
    """
    Parse Python code and verify that it strictly conforms to sandbox rules.
    """
    clean_code = code.strip()
    if not clean_code:
        raise PandasSandboxError("Empty Python code provided.")

    try:
        tree = ast.parse(clean_code)
    except SyntaxError as exc:
        raise PandasSandboxError(f"Syntax error in Python code: {str(exc)}") from exc

    visitor = SandboxSecurityVisitor()
    visitor.visit(tree)

    if not visitor.assigns_to_result:
        raise PandasSandboxError(
            "Code must assign the final analytical output to a variable named 'result' (e.g. `result = df.groupby(...)`)."
        )

def execute_sandboxed_pandas(
    code: str,
    dataframes: Dict[str, pd.DataFrame],
    default_df_name: Optional[str] = None,
    timeout_seconds: int = 5,
) -> pd.DataFrame:
    """
    Execute sanitized pandas Python code in an isolated subprocess worker with timeout and memory isolation.

    Parameters:
        code: Python script to execute.
        dataframes: Dictionary mapping table names to DataFrames.
        default_df_name: Name of default table to map to `df`.
        timeout_seconds: Subprocess execution timeout in seconds.

    Returns:
        pd.DataFrame containing the result.
    """
    # 1. Validate AST safety first
    validate_pandas_code_safety(code)

    # 2. Run in isolated subprocess worker
    with tempfile.TemporaryDirectory() as tmpdir:
        input_pickle = Path(tmpdir) / "input.pkl"
        output_pickle = Path(tmpdir) / "output.pkl"

        payload = {
            "code": code,
            "dataframes": dataframes,
            "default_df_name": default_df_name,
        }

        with open(input_pickle, "wb") as f:
            pickle.dump(payload, f)

        worker_script = Path(__file__).resolve().parent / "pandas_worker.py"
        cmd = [sys.executable, str(worker_script), str(input_pickle), str(output_pickle)]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            logger.error(f"Pandas sandbox execution timed out after {timeout_seconds}s")
            raise PandasSandboxError(f"Execution timed out after {timeout_seconds} seconds.") from exc

        if proc.returncode != 0:
            err_msg = proc.stderr.strip() or proc.stdout.strip() or f"Process exited with code {proc.returncode}"
            # Clean up traceback headers to present a clean message
            lines = [l for l in err_msg.splitlines() if not l.startswith("Traceback")]
            clean_err = lines[-1] if lines else err_msg
            logger.error(f"Pandas worker failed: {clean_err}")
            raise PandasSandboxError(f"Execution Error: {clean_err}")

        if not output_pickle.exists():
            raise PandasSandboxError("Execution failed: No result produced by sandbox worker.")

        with open(output_pickle, "rb") as f:
            result_df = pickle.load(f)

        return result_df
