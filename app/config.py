"""Application configuration management."""

import os
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

class AppConfig(BaseModel):
    """Runtime configuration for the AI Data Analyst application."""

    # Groq API settings
    groq_api_key: str = Field(
        default_factory=lambda: os.getenv("GROQ_API_KEY", "")
    )
    groq_model: str = Field(
        default_factory=lambda: os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    )
    groq_fallback_model: str = Field(
        default_factory=lambda: os.getenv("GROQ_FALLBACK_MODEL", "openai/gpt-oss-20b")
    )

    # Agent execution limits
    max_tool_iterations: int = Field(
        default_factory=lambda: int(os.getenv("MAX_TOOL_ITERATIONS", "5"))
    )
    query_timeout_seconds: int = Field(
        default_factory=lambda: int(os.getenv("QUERY_TIMEOUT_SECONDS", "15"))
    )
    max_preview_rows: int = Field(
        default_factory=lambda: int(os.getenv("MAX_PREVIEW_ROWS", "50"))
    )
    max_llm_result_rows: int = Field(
        default_factory=lambda: int(os.getenv("MAX_LLM_RESULT_ROWS", "15"))
    )

    # Data ingestion constraints
    max_file_size_mb: int = Field(
        default_factory=lambda: int(os.getenv("MAX_FILE_SIZE_MB", "50"))
    )

    # Utilities
    enable_cache: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_CACHE", "true").lower() in ("true", "1", "yes")
    )
    log_level: str = Field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO")
    )
    logs_dir: Path = BASE_DIR / "logs"

    def is_groq_configured(self) -> bool:
        """Check if a valid Groq API key is present."""
        return bool(self.groq_api_key and self.groq_api_key.strip() and self.groq_api_key != "your_groq_api_key_here")

# Global singleton configuration instance
settings = AppConfig()
