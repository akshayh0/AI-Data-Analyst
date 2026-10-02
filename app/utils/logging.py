"""Structured application logging configuration."""

import logging
import sys
from pathlib import Path
from typing import Optional

_logger: Optional[logging.Logger] = None

def setup_logger(log_level: str = "INFO", logs_dir: Optional[Path] = None) -> logging.Logger:
    """Configure and return the root application logger."""
    global _logger
    if _logger is not None:
        return _logger

    logger = logging.getLogger("ai_data_analyst")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    logger.propagate = False

    # Avoid duplicate handlers if re-executed
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler
    if logs_dir is None:
        logs_dir = Path(__file__).resolve().parent.parent.parent / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "app.log"

    try:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as exc:
        print(f"Warning: Unable to create log file at {log_file}: {exc}", file=sys.stderr)

    _logger = logger
    return _logger

def get_logger() -> logging.Logger:
    """Get or initialize the application logger."""
    global _logger
    if _logger is None:
        return setup_logger()
    return _logger
