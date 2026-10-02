"""Deterministic mock provider to simulate complete 6-question run for testing and offline UI demo."""

import json
from typing import Any, Dict, List, Optional
from app.llm.base import LLMMessage, LLMProvider, LLMResponse, ToolCall, TokenUsage

QUESTIONS = [
    "Which region generated the highest revenue?",
    "Show monthly sales trends.",
    "Which products are underperforming?",
    "What are the top five customers?",
    "Generate SQL for this analysis.",
    "Detect anomalies in the dataset.",
]

class SmokeTestMockProvider(LLMProvider):
    """Deterministic mock provider answering the analytical questions for tests and offline mode."""
    def __init__(self):
        self.step_counters = {q: 0 for q in QUESTIONS}

    def get_model_name(self) -> str:
        return "mock-llama-3.3-70b-analyst"

    def generate(self, messages: List[LLMMessage], tools=None, temperature: float = 0.1, max_tokens: int = 1024) -> LLMResponse:
        # Determine current user question
        user_msg = ""
        for m in reversed(messages):
            if m.role == "user":
                user_msg = m.content
                break

        last_msg = messages[-1] if messages else LLMMessage(role="user", content="")

        # 1. Highest revenue region
        if "highest revenue" in user_msg.lower() or "region" in user_msg.lower():
            if last_msg.role == "user":
                return LLMResponse(
                    content="",
                    tool_calls=[ToolCall(
                        id="call_sql_1",
                        name="execute_sql",
                        arguments={
                            "sql": "SELECT c.region, ROUND(SUM(s.revenue), 2) as total_revenue, COUNT(s.order_id) as order_count FROM sales s JOIN customers c ON s.customer_id = c.customer_id GROUP BY c.region ORDER BY total_revenue DESC"
                        }
                    )],
                    usage=TokenUsage(total_tokens=120)
                )
            return LLMResponse(
                content=json.dumps({
                    "answer": "The West region generated the highest revenue at $674,429.67 across 655 orders.",
                    "insights": ["West region leads all territories in total sales", "North and South regions follow closely"],
                    "reasoning": "Joined sales with customers table on customer_id, grouped by region, summed revenue."
                }),
                usage=TokenUsage(total_tokens=140)
            )

        # 2. Monthly sales trends
        elif "monthly" in user_msg.lower() or "trends" in user_msg.lower():
            if last_msg.role == "user":
                return LLMResponse(
                    content="",
                    tool_calls=[ToolCall(
                        id="call_sql_2",
                        name="execute_sql",
                        arguments={
                            "sql": "SELECT strftime(TRY_CAST(order_date AS DATE), '%Y-%m') as ym, ROUND(SUM(revenue), 2) as monthly_revenue FROM sales GROUP BY ym ORDER BY ym"
                        }
                    )],
                    usage=TokenUsage(total_tokens=110)
                )
            elif last_msg.role == "tool" and self.step_counters.get("Show monthly sales trends.", 0) == 0:
                self.step_counters["Show monthly sales trends."] = 1
                return LLMResponse(
                    content="",
                    tool_calls=[ToolCall(
                        id="call_chart_1",
                        name="make_chart",
                        arguments={
                            "chart_type": "line",
                            "x": "ym",
                            "y": "monthly_revenue",
                            "title": "Monthly Revenue Trend"
                        }
                    )],
                    usage=TokenUsage(total_tokens=85)
                )
            return LLMResponse(
                content=json.dumps({
                    "answer": "Monthly sales peaked in November 2023 with $730,918.48, demonstrating seasonal Q4 growth.",
                    "insights": ["Consistent upward trajectory through Q3 and Q4", "Q1 exhibits typical seasonal contraction"],
                    "reasoning": "Grouped order dates by year-month and calculated aggregated revenue trends over 24 months."
                }),
                usage=TokenUsage(total_tokens=160)
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
                    "answer": "The lowest revenue products are PROD-0181 ($0.00, 0 units) and PROD-0091 ($0.00, 0 units).",
                    "insights": ["Zero-revenue products indicate unpurchased inventory", "Inventory rebalancing advised for low velocity items"],
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
                            "sql": "SELECT c.customer_name, ROUND(SUM(s.revenue), 2) as total_spend FROM sales s JOIN customers c ON s.customer_id = c.customer_id GROUP BY c.customer_name ORDER BY total_spend DESC LIMIT 5"
                        }
                    )],
                    usage=TokenUsage(total_tokens=125)
                )
            return LLMResponse(
                content=json.dumps({
                    "answer": "The top 5 customers by total spend are Karen Harris ($394,688.75), Karen Williams ($249,770.62), Steven Williams ($99,867.84), Paul Hernandez ($15,676.26), and Karen White ($15,285.03).",
                    "insights": ["Top accounts contribute a significant share of total sales", "Key account management recommended for top tier"],
                    "reasoning": "Aggregated customer revenue through sales join and filtered top 5."
                }),
                usage=TokenUsage(total_tokens=160)
            )

        # 5. Generate SQL
        elif "generate sql" in user_msg.lower() or "sql for this analysis" in user_msg.lower():
            return LLMResponse(
                content=json.dumps({
                    "answer": "Here is the SQL query to analyze customer revenue by region with profit margins:\n\n```sql\nSELECT \n    c.region,\n    COUNT(DISTINCT s.order_id) as total_orders,\n    ROUND(SUM(s.revenue), 2) as total_revenue,\n    ROUND(SUM(s.profit), 2) as total_profit,\n    ROUND(SUM(s.profit) / NULLIF(SUM(s.revenue), 0) * 100, 2) as profit_margin_pct\nFROM sales s\nJOIN customers c ON s.customer_id = c.customer_id\nGROUP BY c.region\nORDER BY total_revenue DESC;\n```",
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
                    "insights": ["Pricing errors and bulk volume spikes caught", "Multi-method ensemble validated severe anomalies"],
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
