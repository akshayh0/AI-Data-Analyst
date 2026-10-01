"""Live smoke test running the 6 required example questions against Groq API and saving transcripts."""

from datetime import datetime
import json
import os
from pathlib import Path
import sys
from dotenv import load_dotenv

# Ensure app is in path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
load_dotenv()

from app.agent import DataAnalystAgent
from app.config import settings
from app.data.loader import load_csv_file
from app.llm.groq_provider import GroqProvider
from app.tools.sql_tool import DuckDBManager
from app.utils.logging import setup_logger

logger = setup_logger(log_level="INFO")

QUESTIONS = [
    "Which region generated the highest revenue?",
    "Show monthly sales trends.",
    "Which products are underperforming?",
    "What are the top five customers?",
    "Generate SQL for this analysis.",
    "Detect anomalies in the dataset.",
]

def run_live_smoke_test():
    print("=" * 70)
    print("AI DATA ANALYST - LIVE SMOKE TEST")
    print("=" * 70)

    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key or api_key == "your_groq_api_key_here":
        print("\n[!] WARNING: GROQ_API_KEY is not configured in .env or environment.")
        print("Please add your key to .env: GROQ_API_KEY=gsk_...")
        print("Live smoke test against real Groq API will be skipped until key is supplied.")
        print("Unit test suite with mock LLM verifies full agent loop and tool execution.\n")
        return

    print(f"Connecting to Groq API using model: {settings.groq_model} (fallback: {settings.groq_fallback_model})")
    llm = GroqProvider(api_key=api_key, model=settings.groq_model, fallback_model=settings.groq_fallback_model)
    db = DuckDBManager()

    # Load sample datasets
    data_dir = BASE_DIR / "sample_data"
    profiles = {}

    for csv_file in ["customers.csv", "products.csv", "sales.csv"]:
        file_path = data_dir / csv_file
        if not file_path.exists():
            print(f"Error: {file_path} not found.")
            return

        df, profile, table_name, mapping = load_csv_file(file_path)
        db.register_dataframe(table_name, df)
        profiles[table_name] = profile
        print(f"Loaded '{table_name}': {len(df):,} rows, {len(df.columns)} columns")

    agent = DataAnalystAgent(llm, db, profiles)
    transcripts = []

    out_dir = BASE_DIR / "evals" / "transcripts"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("\nExecuting 6 Assignment Example Questions:\n" + "-" * 70)

    for idx, question in enumerate(QUESTIONS, 1):
        print(f"\n[{idx}/6] Question: {question}")
        t0 = datetime.now()
        try:
            result = agent.ask(question)
            elapsed = (datetime.now() - t0).total_seconds()

            print(f"Iterations: {result.iterations_used} | Tokens: {result.total_tokens_used} | Time: {elapsed:.2f}s")
            print(f"Tools called: {result.tool_calls_made}")
            if result.sql_executed:
                print(f"SQL Executed:\n{result.sql_executed}")
            print(f"\nFinal Answer Preview:\n{result.answer[:300]}...\n")

            transcripts.append({
                "question_index": idx,
                "question": question,
                "iterations": result.iterations_used,
                "tokens": result.total_tokens_used,
                "elapsed_seconds": elapsed,
                "tools_called": result.tool_calls_made,
                "sql_executed": result.sql_executed,
                "pandas_executed": result.pandas_executed,
                "chart_spec": result.chart_spec,
                "answer": result.answer,
                "unsupported_numbers": result.unsupported_numbers,
            })
        except Exception as exc:
            print(f"Error answering '{question}': {exc}")
            transcripts.append({
                "question_index": idx,
                "question": question,
                "error": str(exc),
            })

    # Save transcripts
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    transcript_file = out_dir / f"smoke_test_{timestamp_str}.json"
    with open(transcript_file, "w", encoding="utf-8") as f:
        json.dump(transcripts, f, indent=2)

    print(f"\n[OK] Smoke test completed. Transcripts saved to: {transcript_file}")

if __name__ == "__main__":
    run_live_smoke_test()
