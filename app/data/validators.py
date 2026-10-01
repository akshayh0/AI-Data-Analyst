"""Data validation, encoding detection, delimiter sniffing, and SQL column sanitization."""

import csv
import io
import re
from typing import Dict, List, Optional, Tuple
import chardet
import pandas as pd
from app.config import settings

class ValidationError(Exception):
    """Raised when data validation fails."""
    pass

def detect_encoding(raw_bytes: bytes) -> str:
    """
    Detect the character encoding of raw file bytes.
    Defaults to utf-8 if confidence is low or detection fails.
    """
    if not raw_bytes:
        return "utf-8"

    # Sample first 64KB for speed
    sample = raw_bytes[:65536]
    result = chardet.detect(sample)
    encoding = result.get("encoding")

    if not encoding or result.get("confidence", 0) < 0.5:
        # Try common encodings
        for candidate in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
            try:
                sample.decode(candidate)
                return candidate
            except (UnicodeDecodeError, LookupError):
                continue
        return "utf-8"

    # Normalize utf-8-sig / ISO variations / ascii
    encoding_lower = encoding.lower()
    if "utf-8" in encoding_lower or "ascii" in encoding_lower:
        return "utf-8"
    return encoding

def detect_delimiter(sample_text: str) -> str:
    """
    Sniff the delimiter used in a CSV text sample.
    Supports comma, semicolon, tab, and pipe.
    """
    if not sample_text.strip():
        return ","

    try:
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample_text, delimiters=",\t;|")
        return dialect.delimiter
    except Exception:
        # Fallback: count candidate delimiters in first few non-empty lines
        lines = [line for line in sample_text.splitlines() if line.strip()][:5]
        delimiters = [",", "\t", ";", "|"]
        counts = {d: sum(line.count(d) for line in lines) for d in delimiters}
        best = max(counts, key=counts.get)
        return best if counts[best] > 0 else ","

def sanitize_column_name(col: str, index: int) -> str:
    """
    Convert an arbitrary column name into a safe, deterministic SQL identifier.
    Examples:
        'Customer ID' -> 'customer_id'
        'Sales ($)' -> 'sales_usd'
        '1st_order' -> 'col_1st_order'
        '' -> 'col_1'
    """
    if col is None:
        col = ""
    col_str = str(col).strip()

    if not col_str:
        return f"col_{index + 1}"

    # Replace common currency / math symbols with text
    symbol_map = {
        "$": "_usd",
        "€": "_eur",
        "£": "_gbp",
        "%": "_pct",
        "#": "_num",
        "@": "_at",
        "&": "_and",
        "+": "_plus",
        "/": "_per_",
    }
    for sym, rep in symbol_map.items():
        col_str = col_str.replace(sym, rep)

    # Convert to lowercase and replace non-alphanumeric with underscore
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", col_str.lower())
    # Collapse multiple underscores
    sanitized = re.sub(r"_+", "_", sanitized).strip("_")

    if not sanitized:
        return f"col_{index + 1}"

    # If starts with a digit, prefix with col_
    if sanitized[0].isdigit():
        sanitized = f"col_{sanitized}"

    # Reserved SQL keywords check
    reserved_keywords = {
        "select", "table", "group", "order", "where", "from", "join", "limit",
        "create", "drop", "alter", "delete", "insert", "update", "case", "when",
        "then", "else", "end", "user", "index", "primary", "foreign", "key",
        "check", "default", "null", "all", "and", "or", "not", "as", "by", "on"
    }
    if sanitized in reserved_keywords:
        sanitized = f"{sanitized}_col"

    return sanitized

def clean_column_names(columns: List[str]) -> Tuple[List[str], Dict[str, str]]:
    """
    Sanitize a list of column names, ensuring uniqueness and SQL safety.
    Returns:
        (cleaned_columns_list, mapping_dict_original_to_cleaned)
    """
    seen_names: Dict[str, int] = {}
    cleaned_columns: List[str] = []
    mapping: Dict[str, str] = {}

    for idx, raw_col in enumerate(columns):
        clean_name = sanitize_column_name(raw_col, idx)

        # Ensure uniqueness
        if clean_name in seen_names:
            seen_names[clean_name] += 1
            unique_name = f"{clean_name}_{seen_names[clean_name]}"
        else:
            seen_names[clean_name] = 0
            unique_name = clean_name

        cleaned_columns.append(unique_name)
        mapping[str(raw_col)] = unique_name

    return cleaned_columns, mapping

def validate_file_metadata(filename: str, file_size_bytes: int, max_size_mb: Optional[int] = None) -> None:
    """
    Validate basic file attributes before reading full content.
    """
    if max_size_mb is None:
        max_size_mb = settings.max_file_size_mb

    if not filename.lower().endswith(".csv"):
        raise ValidationError(f"File '{filename}' is not a CSV file. Only .csv files are supported.")

    if file_size_bytes == 0:
        raise ValidationError(f"File '{filename}' is empty (0 bytes).")

    max_bytes = max_size_mb * 1024 * 1024
    if file_size_bytes > max_bytes:
        raise ValidationError(
            f"File '{filename}' ({file_size_bytes / (1024*1024):.1f} MB) exceeds maximum allowed size of {max_size_mb} MB."
        )

def sanitize_table_name(filename: str) -> str:
    """
    Generate a clean SQL table name from a file name.
    Example: '2024-Sales Data (v2).csv' -> 'sales_data_v2'
    """
    stem = re.sub(r"\.[^.]+$", "", filename).strip()
    clean = re.sub(r"[^a-zA-Z0-9_]", "_", stem.lower())
    clean = re.sub(r"_+", "_", clean).strip("_")

    if not clean:
        return "uploaded_table"

    if clean[0].isdigit():
        clean = f"t_{clean}"

    reserved_keywords = {
        "select", "table", "group", "order", "where", "from", "join", "limit",
        "create", "drop", "alter", "delete", "insert", "update", "case", "when",
        "then", "else", "end", "user", "index", "primary", "foreign", "key",
        "check", "default", "null", "all", "and", "or", "not", "as", "by", "on"
    }
    if clean in reserved_keywords:
        clean = f"{clean}_table"

    return clean
