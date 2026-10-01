"""Live smoke test running the 6 required example questions against Groq API and saving transcripts."""

import argparse
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
from app.llm.base import LLMMessage, LLMProvider, LLMResponse, ToolCall, TokenUsage
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

class SmokeTestMockProvider(LLMProvider):
    """Deterministic mock provider to simulate complete 6-question run when running offline."""
    def __init__(self):
        self.step_counters = {q: 0 for q in QUESTIONS}

    def get_model_name(self) -> str:
        return "mock-llama-3.3-70b-analyst"

    def generate(self, messages, tools=None, temperature=0.1, max_tokens=1024):
        # Determine current user question
        user_msg = next((m.content for m in reversed(messages) if m.role == "user"), "")
        last_msg = messages[-1]

        # 1. Highest revenue region
        if "region" in user_msg.lower():
            if last_msg.role == "user":
                return LLMResponse(
                    content="",
                    tool_calls=[ToolCall(
                        id="call_reg_1",
                        name="execute_sql",
                        arguments={
                            "sql": "SELECT c.region, ROUND(SUM(s.revenue), 2) as total_revenue FROM sales s JOIN customers c ON s.customer_id = c.customer_id GROUP BY c.region ORDER BY total_revenue DESC LIMIT 5"
                        }
                    )],
                    usage=TokenUsage(total_tokens=120)
                )
            return LLMResponse(
                content=json.dumps({
                    "answer": "The North region generated the highest revenue with $638,474.32 in sales, followed by South with $512,189.40.",
                    "insights": ["North region leads overall sales volume", "South and East follow closely behind"],
                    "reasoning": "Joined sales with customers on customer_id, aggregated sum of revenue grouped by region and sorted descending."
                }),
                usage=TokenUsage(total_tokens=150)
            )

        # 2. Monthly sales trends
        elif "monthly" in user_msg.lower():
            if last_msg.role == "user":
                return LLMResponse(
                    content="",
                    tool_calls=[ToolCall(
                        id="call_mth_1",
                        name="execute_sql",
                        arguments={
                            "sql": "SELECT strftime(order_date, '%Y-%m') as sales_month, ROUND(SUM(revenue), 2) as total_revenue FROM sales GROUP BY sales_month ORDER BY sales_month"
                        }
                    )],
                    usage=TokenUsage(total_tokens=110)
                )
            elif "make_chart" not in [t.name for t in (messages[-2].tool_calls or [])]:
                return LLMResponse(
                    content="",
                    tool_calls=[ToolCall(
                        id="call_chart_1",
                        name="make_chart",
                        arguments={
                            "chart_type": "line",
                            "x": "sales_month",
                            "y": "total_revenue",
                            "title": "Monthly Revenue Trends"
                        }
                    )],
                    usage=TokenUsage(total_tokens=90)
                )
            return LLMResponse(
                content=json.dumps({
                    "answer": "Monthly revenue remained steady between $140,000 and $180,000 across early 2024, peaking in March.",
                    "insights": ["Peak sales observed in March 2024", "Steady month-over-month performance"],
                    "reasoning": "Aggregated sales by formatted year-month and charted timeline."
                }),
                usage=TokenUsage(total_tokens=140)
            )

        # 3. Underperforming products
        elif "underperforming" in user_msg.lower():
            if last_msg.role == "user":
                return LLMResponse(
                    content="",
                    tool_calls=[ToolCall(
                        id="call_prod_1",
                        name="execute_sql",
                        arguments={
                            "sql": "SELECT p.product_name, p.category, ROUND(SUM(s.revenue), 2) as total_revenue, SUM(s.quantity) as units_sold FROM products p LEFT JOIN sales s ON p.product_id = s.product_id GROUP BY p.product_name, p.category ORDER BY total_revenue ASC LIMIT 5"
                        }
                    )],
                    usage=TokenUsage(total_tokens=130)
                )
            return LLMResponse(
                content=json.dumps({
                    "answer": "The lowest revenue products are 'Ergonomic Mouse' ($450.00, 15 units) and 'Basic HDMI Cable' ($520.00, 26 units).",
                    "insights": ["Accessories category has lowest revenue per SKU", "Inventory rebalancing advised for low velocity items"],
                    "reasoning": "Left joined products with sales, aggregated revenue and units sold, sorted ascending."
                }),
                usage=TokenUsage(total_tokens=150)
            )

        # 4. Top five customers
        elif "top five customers" in user_msg.lower():
            if last_msg.role == "user":
                return LLMResponse(
                    content="",
                    tool_calls=[ToolCall(
                        id="call_cust_1",
                        name="execute_sql",
                        arguments={
                            "sql": "SELECT c.name, c.company, ROUND(SUM(s.revenue), 2) as total_spend FROM sales s JOIN customers c ON s.customer_id = c.customer_id GROUP BY c.name, c.company ORDER BY total_spend DESC LIMIT 5"
                        }
                    )],
                    usage=TokenUsage(total_tokens=125)
                )
            return LLMResponse(
                content=json.dumps({
                    "answer": "The top 5 customers by total spend are GlobalCorp ($48,210.50), TechSolutions ($42,150.00), Apex Retail ($39,800.20), Summit Logistics ($36,450.00), and BlueSky Inc ($34,120.00).",
                    "insights": ["Top 5 accounts contribute over 18% of enterprise revenue", "Key account management recommended for top tier"],
                    "reasoning": "Aggregated customer revenue through sales join and filtered top 5."
                }),
                usage=TokenUsage(total_tokens=160)
            )

        # 5. Generate SQL
        elif "generate sql" in user_msg.lower() or "sql for this analysis" in user_msg.lower():
            return LLMResponse(
                content=json.dumps({
                    "answer": "Here is the production SQL query to analyze customer revenue by region with profit margins:\n\n```sql\nSELECT \n    c.region,\n    COUNT(DISTINCT s.order_id) as total_orders,\n    ROUND(SUM(s.revenue), 2) as total_revenue,\n    ROUND(SUM(s.profit), 2) as total_profit,\n    ROUND(SUM(s.profit) / NULLIF(SUM(s.revenue), 0) * 100, 2) as profit_margin_pct\nFROM sales s\nJOIN customers c ON s.customer_id = c.customer_id\nGROUP BY c.region\nORDER BY total_revenue DESC;\n```",
                    "insights": ["Calculates order volume, revenue, profit, and margin per region", "Uses NULLIF to safeguard against division by zero"],
                    "reasoning": "Constructed multi-table analytical query with safety guards and aggregation."
                }),
                usage=TokenUsage(total_tokens=180)
            )

        # 6. Detect anomalies
        elif "anomalies" in user_msg.lower():
            if last_msg.role == "user":
                return LLMResponse(
                    content="",
                    tool_calls=[ToolCall(
                        id="call_anom_1",
                        name="detect_anomalies",
                        arguments={
                            "table": "sales",
                            "columns": ["quantity", "revenue", "profit", "discount"]
                        }
                    )],
                    usage=TokenUsage(total_tokens=100)
                )
            return LLMResponse(
                content=json.dumps({
                    "answer": "Identified critical anomalies in sales: ORD-00389 experienced an extreme -$25,000.00 loss due to 90% discount, while ORD-00142 and ORD-00804 had massive bulk quantities (>500 units) far above the norm.",
                    "insights": ["Planted critical pricing errors and bulk volume spikes caught", "Multi-method ensemble validated all severe anomalies with high confidence"],
                    "reasoning": "Executed anomaly tool combining IQR, Modified Z-score, Isolation Forest, and relative margin rules."
                }),
                usage=TokenUsage(total_tokens=170)
            )

        return LLMResponse(
            content=json.dumps({
                "answer": "Analysis completed.",
                "insights": ["Data processed successfully"],
                "reasoning": "Standard response."
            }),
            usage=TokenUsage(total_tokens=50)
        )

def run_live_smoke_test(use_mock: bool = False):
    print("=" * 70)
    print("AI DATA ANALYST - LIVE SMOKE TEST")
    print("=" * 70)

    api_key = os.getenv("GROQ_API_KEY", "")
    is_real = bool(api_key and api_key != "your_groq_api_key_here") and not use_mock

    if is_real:
        print(f"Connecting to Groq API using model: {settings.groq_model} (fallback: {settings.groq_fallback_model})")
        llm = GroqProvider(api_key=api_key, model=settings.groq_model, fallback_model=settings.groq_fallback_model)
    else:
        print("\n[INFO] Running in mock/offline mode (Simulated LLM Provider).")
        if not api_key or api_key == "your_groq_api_key_here":
            print("Note: To run against real Groq API, add your key to .env: GROQ_API_KEY=gsk_...")
        llm = SmokeTestMockProvider()

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
                "status": "SUCCESS",
            })
        except Exception as exc:
            print(f"Error answering '{question}': {exc}")
            transcripts.append({
                "question_index": idx,
                "question": question,
                "status": "FAILED",
                "error": str(exc),
            })

    # Save transcripts
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    mode_str = "real" if is_real else "mock"
    transcript_file = out_dir / f"smoke_test_{mode_str}_{timestamp_str}.json"
    with open(transcript_file, "w", encoding="utf-8") as f:
        json.dump(transcripts, f, indent=2)

    print(f"\n[OK] Smoke test completed. Transcripts saved to: {transcript_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run live smoke test")
    parser.add_argument("--mock", action="store_true", help="Run with mock LLM provider")
    args = parser.parse_args()
    run_live_smoke_test(use_mock=args.mock)
