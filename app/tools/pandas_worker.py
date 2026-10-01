"""Isolated worker process for running sandboxed pandas/numpy scripts."""

import pickle
import sys
import pandas as pd
import numpy as np
from typing import Any, Dict

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

def main():
    if len(sys.argv) < 3:
        sys.stderr.write("Usage: python pandas_worker.py <input_pickle_path> <output_pickle_path>\n")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    with open(input_path, "rb") as f:
        payload = pickle.load(f)

    code = payload["code"]
    dataframes = payload["dataframes"]
    default_df_name = payload.get("default_df_name")

    safe_globals = {
        "__builtins__": SAFE_BUILTINS,
        "pd": pd,
        "np": np,
    }

    local_scope: Dict[str, Any] = {}
    for name, df in dataframes.items():
        local_scope[name] = df.copy(deep=True)

    if default_df_name and default_df_name in local_scope:
        local_scope["df"] = local_scope[default_df_name]
    elif dataframes:
        first_table = next(iter(dataframes.keys()))
        local_scope["df"] = local_scope[first_table]

    compiled_code = compile(code, "<sandboxed_pandas_worker>", "exec")
    exec(compiled_code, safe_globals, local_scope)

    raw_result = local_scope.get("result")
    if raw_result is None:
        raise ValueError("Execution completed but 'result' variable was None or not assigned.")

    if isinstance(raw_result, pd.DataFrame):
        final_df = raw_result
    elif isinstance(raw_result, pd.Series):
        final_df = raw_result.to_frame(name=raw_result.name or "value")
    elif isinstance(raw_result, (int, float, str, bool, np.number)):
        final_df = pd.DataFrame([{"result": raw_result}])
    elif isinstance(raw_result, (list, tuple)):
        final_df = pd.DataFrame(raw_result)
    elif isinstance(raw_result, dict):
        final_df = pd.DataFrame([raw_result])
    else:
        final_df = pd.DataFrame([{"result": str(raw_result)}])

    with open(output_path, "wb") as f:
        pickle.dump(final_df, f)

if __name__ == "__main__":
    main()
