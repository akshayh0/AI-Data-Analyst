"""Isolated worker process for running sandboxed pandas/numpy scripts with strict memory limits."""

import os
import pickle
import platform
import sys
import threading
import time
from typing import Any, Dict
import numpy as np
import pandas as pd

# Default memory cap: 256 MB
DEFAULT_MEMORY_CAP_BYTES = 256 * 1024 * 1024

def set_memory_limit(max_bytes: int = DEFAULT_MEMORY_CAP_BYTES):
    """
    Apply real memory limits across operating systems:
    - On Linux/Unix: Uses resource.setrlimit(resource.RLIMIT_AS, ...)
    - On Windows: Spawns a high-frequency memory watchdog thread using ctypes
    """
    # 1. Linux / Unix
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (max_bytes, max_bytes))
        return
    except (ImportError, AttributeError, ValueError, OSError):
        pass

    # 2. Windows via high-frequency memory watchdog checking WorkingSetSize (resident RAM)
    if platform.system() == "Windows":
        try:
            import ctypes
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            get_mem_info = getattr(ctypes.windll.psapi, "GetProcessMemoryInfo", None) or getattr(
                ctypes.windll.kernel32, "K32GetProcessMemoryInfo", None
            )
            if get_mem_info:
                get_mem_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
                get_mem_info.restype = wintypes.BOOL

            def memory_watchdog():
                current_process = ctypes.windll.kernel32.GetCurrentProcess()
                counters = PROCESS_MEMORY_COUNTERS()
                counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
                while True:
                    if get_mem_info and get_mem_info(current_process, ctypes.byref(counters), counters.cb):
                        # WorkingSetSize measures actual physical RAM occupied by this process
                        if counters.WorkingSetSize > max_bytes:
                            sys.stderr.write(
                                f"MemoryLimitExceeded: Process exceeded memory limit of {max_bytes / (1024*1024):.0f}MB (used {counters.WorkingSetSize / (1024*1024):.1f}MB)\n"
                            )
                            os._exit(1)
                    time.sleep(0.01)

            t = threading.Thread(target=memory_watchdog, daemon=True)
            t.start()
        except Exception as e:
            sys.stderr.write(f"Warning: Could not configure Windows memory watcher: {e}\n")

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

    # Enforce memory cap before processing user payload
    set_memory_limit(DEFAULT_MEMORY_CAP_BYTES)

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

    try:
        compiled_code = compile(code, "<sandboxed_pandas_worker>", "exec")
        exec(compiled_code, safe_globals, local_scope)
    except MemoryError:
        sys.stderr.write("MemoryError: Script exceeded available memory allocation limits.\n")
        sys.exit(1)
    except Exception as exc:
        sys.stderr.write(f"{type(exc).__name__}: {str(exc)}\n")
        sys.exit(1)

    raw_result = local_scope.get("result")
    if raw_result is None:
        sys.stderr.write("ValueError: Execution completed but 'result' variable was None or not assigned.\n")
        sys.exit(1)

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
