"""CSV loading, decoding, parsing, and table ingestion pipeline."""

import io
from pathlib import Path
from typing import BinaryIO, Dict, Optional, Tuple, Union
import pandas as pd

from app.data.profiler import TableProfile, profile_dataframe
from app.data.validators import (
    ValidationError,
    clean_column_names,
    detect_delimiter,
    detect_encoding,
    sanitize_table_name,
    validate_file_metadata,
)
from app.utils.logging import get_logger

logger = get_logger()

def load_csv_file(
    file_source: Union[str, Path, BinaryIO, bytes],
    filename: Optional[str] = None,
    max_size_mb: Optional[int] = None,
) -> Tuple[pd.DataFrame, TableProfile, str, Dict[str, str]]:
    """
    Validate, decode, parse, sanitize and profile an uploaded CSV.

    Parameters:
        file_source: File path, open binary stream, or raw bytes.
        filename: Optional explicit filename (required if passing raw bytes/stream).
        max_size_mb: Configurable file size ceiling.

    Returns:
        (df, table_profile, sanitized_table_name, column_mapping)
    """
    # 1. Resolve raw bytes and filename
    if isinstance(file_source, (str, Path)):
        path = Path(file_source)
        resolved_filename = path.name if filename is None else filename
        with open(path, "rb") as f:
            raw_bytes = f.read()
    elif isinstance(file_source, bytes):
        if not filename:
            raise ValidationError("Filename must be provided when loading from raw bytes.")
        resolved_filename = filename
        raw_bytes = file_source
    else:
        # File-like object (e.g., Streamlit UploadedFile)
        resolved_filename = getattr(file_source, "name", filename or "uploaded.csv")
        file_source.seek(0)
        raw_bytes = file_source.read()

    file_size_bytes = len(raw_bytes)
    logger.info(f"Ingesting file '{resolved_filename}' ({file_size_bytes:,} bytes)")

    # 2. Basic metadata validation
    validate_file_metadata(resolved_filename, file_size_bytes, max_size_mb)

    # 3. Detect encoding
    encoding = detect_encoding(raw_bytes)
    logger.debug(f"Detected encoding '{encoding}' for '{resolved_filename}'")

    try:
        sample_text = raw_bytes[:16384].decode(encoding, errors="replace")
    except Exception as exc:
        logger.warning(f"Failed to decode sample text with {encoding}: {exc}, falling back to utf-8")
        encoding = "utf-8"
        sample_text = raw_bytes[:16384].decode("utf-8", errors="replace")

    # 4. Sniff delimiter
    delimiter = detect_delimiter(sample_text)
    logger.debug(f"Detected delimiter '{delimiter}' for '{resolved_filename}'")

    # 5. Parse into Pandas DataFrame
    try:
        df = pd.read_csv(
            io.BytesIO(raw_bytes),
            encoding=encoding,
            sep=delimiter,
            low_memory=False,
            on_bad_lines="skip",
        )
    except Exception as exc:
        raise ValidationError(f"Failed to parse CSV file '{resolved_filename}': {str(exc)}") from exc

    if df.empty and len(df.columns) == 0:
        raise ValidationError(f"File '{resolved_filename}' has no data or columns.")

    # 6. Sanitize column names
    original_columns = [str(c) for c in df.columns]
    cleaned_columns, col_mapping = clean_column_names(original_columns)
    df.columns = cleaned_columns

    # 7. Sanitize table name
    table_name = sanitize_table_name(resolved_filename)

    # 8. Profile the DataFrame
    profile = profile_dataframe(
        df=df,
        table_name=table_name,
        filename=resolved_filename,
        column_mapping=col_mapping,
    )

    logger.info(f"Successfully loaded '{table_name}' with {len(df):,} rows and {len(df.columns)} columns.")
    return df, profile, table_name, col_mapping
