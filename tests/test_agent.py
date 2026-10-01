"""Unit tests for DataAnalystAgent using Mock LLM provider."""

from typing import Any, Dict, List, Optional
import pandas as pd
import pytest

from app.agent import DataAnalystAgent
from app.data.profiler import profile_dataframe
from app.llm.base import LLMMessage, LLMProvider, LLMResponse, TokenUsage, ToolCall
from app.tools.sql_tool import DuckDBManager

class MockLLMProvider(LLMProvider):
    """Predictable mock LLM provider for unit testing agent flows."""

    def __init__(self, responses: List[LLMResponse]):
        self.responses = list(responses)
        self.call_count = 0
        self.recorded_messages: List[List[LLMMessage]] = []

    def get_model_name(self) -> str:
        return "mock-llama-70b"

    def generate(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        self.call_count += 1
        self.recorded_messages.append(list(messages))
        if not self.responses:
            return LLMResponse(content="No more mock responses scheduled.")
        return self.responses.pop(0)

@pytest.fixture
def agent_environment():
    db = DuckDBManager()
    sales_df = pd.DataFrame({
        "order_id": ["ORD-1", "ORD-2", "ORD-3", "ORD-4"],
        "customer_id": ["C-1", "C-2", "C-1", "C-3"],
        "product_id": ["P-1", "P-2", "P-1", "P-3"],
        "revenue": [500.0, 250.0, 150.0, 800.0],
        "channel": ["Online", "Retail", "Online", "Partner"],
    })
    customers_df = pd.DataFrame({
        "customer_id": ["C-1", "C-2", "C-3"],
        "region": ["North", "South", "North"],
    })
    products_df = pd.DataFrame({
        "product_id": ["P-1", "P-2", "P-3"],
        "category": ["Electronics", "Office", "Electronics"],
    })

    db.register_dataframe("sales", sales_df)
    db.register_dataframe("customers", customers_df)
    db.register_dataframe("products", products_df)

    profiles = {
        "sales": profile_dataframe(sales_df, "sales", "sales.csv"),
        "customers": profile_dataframe(customers_df, "customers", "customers.csv"),
        "products": profile_dataframe(products_df, "products", "products.csv"),
    }

    return db, profiles

def test_successful_sql_flow(agent_environment):
    db, profiles = agent_environment

    # Mock response 1: Call SQL tool
    resp1 = LLMResponse(
        content="I will query the revenue by region.",
        tool_calls=[
            ToolCall(
                id="call_1",
                name="run_sql",
                arguments={
                    "query": "SELECT c.region, SUM(s.revenue) as total_rev FROM sales s JOIN customers c ON s.customer_id = c.customer_id GROUP BY c.region ORDER BY total_rev DESC"
                },
            )
        ],
        usage=TokenUsage(prompt_tokens=100, completion_tokens=30, total_tokens=130),
    )
    # Mock response 2: Produce final 5-part answer
    resp2 = LLMResponse(
        content=(
            "### 1. Direct Answer\nThe North region generated the highest revenue ($1,450.00).\n\n"
            "### 2. Key Insights\n- North accounted for 85% of total revenue.\n- South generated $250.00.\n\n"
            "### 3. Visualizations\nNone generated.\n\n"
            "### 4. Code Used\nDuckDB SQL join between sales and customers.\n\n"
            "### 5. How I Got This\nJoined `sales` with `customers` on `customer_id` and summed `revenue` grouped by `region`."
        ),
        usage=TokenUsage(prompt_tokens=150, completion_tokens=60, total_tokens=210),
    )

    mock_llm = MockLLMProvider([resp1, resp2])
    agent = DataAnalystAgent(mock_llm, db, profiles)

    result = agent.ask("Which region generated the highest revenue?")

    assert "North region generated the highest revenue" in result.answer
    assert result.sql_executed is not None
    assert "region" in result.sql_executed
    assert result.data_preview is not None
    assert "North" in list(result.data_preview["region"])
    assert result.iterations_used == 2
    assert result.total_tokens_used == 340

def test_sql_error_self_correction(agent_environment):
    db, profiles = agent_environment

    # Mock response 1: Generates invalid SQL query (wrong column name)
    resp1 = LLMResponse(
        content="Querying region sales...",
        tool_calls=[
            ToolCall(
                id="call_err",
                name="run_sql",
                arguments={"query": "SELECT invalid_column FROM sales"},
            )
        ],
    )
    # Mock response 2: Fixes query upon seeing error
    resp2 = LLMResponse(
        content="Correcting query with valid column...",
        tool_calls=[
            ToolCall(
                id="call_fix",
                name="run_sql",
                arguments={"query": "SELECT revenue FROM sales"},
            )
        ],
    )
    # Mock response 3: Final answer
    resp3 = LLMResponse(
        content="### 1. Direct Answer\nTotal revenue retrieved successfully.",
    )

    mock_llm = MockLLMProvider([resp1, resp2, resp3])
    agent = DataAnalystAgent(mock_llm, db, profiles)

    result = agent.ask("Show revenues")

    assert result.iterations_used == 3
    assert result.data_preview is not None
    assert "revenue" in result.data_preview.columns
    assert "Total revenue retrieved successfully." in result.answer

def test_max_iterations_ceiling(agent_environment):
    db, profiles = agent_environment

    # Infinite tool loop mock: always returns a tool call
    infinite_responses = [
        LLMResponse(
            content=f"Step {i}",
            tool_calls=[ToolCall(id=f"c_{i}", name="run_sql", arguments={"query": "SELECT 1"})],
        )
        for i in range(10)
    ]

    mock_llm = MockLLMProvider(infinite_responses)
    agent = DataAnalystAgent(mock_llm, db, profiles, max_iterations=5)

    result = agent.ask("Run endless queries")

    assert result.iterations_used == 5
    assert "maximum analysis steps" in result.answer

def test_multi_turn_followup_memory(agent_environment):
    db, profiles = agent_environment

    # Turn 1: Region question
    resp1_turn1 = LLMResponse(
        content="Running region query",
        tool_calls=[
            ToolCall(
                id="call_1",
                name="run_sql",
                arguments={"query": "SELECT c.region, SUM(s.revenue) as rev FROM sales s JOIN customers c ON s.customer_id = c.customer_id GROUP BY c.region"},
            )
        ],
    )
    resp2_turn1 = LLMResponse(
        content="Region revenue calculated.",
    )

    # Turn 2: Follow-up question asking for channel breakdown
    resp1_turn2 = LLMResponse(
        content="Breaking down by channel",
        tool_calls=[
            ToolCall(
                id="call_2",
                name="run_sql",
                arguments={"query": "SELECT s.channel, SUM(s.revenue) as rev FROM sales s GROUP BY s.channel"},
            )
        ],
    )
    resp2_turn2 = LLMResponse(
        content="Channel breakdown complete.",
    )

    mock_llm = MockLLMProvider([resp1_turn1, resp2_turn1, resp1_turn2, resp2_turn2])
    agent = DataAnalystAgent(mock_llm, db, profiles)

    res1 = agent.ask("Sales by region?")
    assert "Region revenue calculated." in res1.answer

    res2 = agent.ask("Now break that down by channel")
    assert "Channel breakdown complete." in res2.answer
    assert res2.data_preview is not None
    assert "channel" in res2.data_preview.columns
    # Verify conversation history persisted across turns
    assert len(agent.conversation_history) > 4

def test_multi_file_three_way_join(agent_environment):
    db, profiles = agent_environment

    resp1 = LLMResponse(
        content="Joining sales, customers, and products",
        tool_calls=[
            ToolCall(
                id="call_join",
                name="run_sql",
                arguments={
                    "query": """
                    SELECT c.region, p.category, SUM(s.revenue) as category_rev
                    FROM sales s
                    JOIN customers c ON s.customer_id = c.customer_id
                    JOIN products p ON s.product_id = p.product_id
                    GROUP BY c.region, p.category
                    ORDER BY category_rev DESC
                    """
                },
            )
        ],
    )
    resp2 = LLMResponse(
        content="Three-way multi-file join completed successfully.",
    )

    mock_llm = MockLLMProvider([resp1, resp2])
    agent = DataAnalystAgent(mock_llm, db, profiles)

    result = agent.ask("Revenue by region and product category?")
    assert result.data_preview is not None
    assert "region" in result.data_preview.columns
    assert "category" in result.data_preview.columns
    assert "category_rev" in result.data_preview.columns

def test_groq_provider_rate_limit_retry(monkeypatch):
    from unittest.mock import MagicMock
    from groq import RateLimitError
    from app.llm.groq_provider import GroqProvider

    provider = GroqProvider(api_key="mock_key")
    mock_client = MagicMock()

    # Create mock response object
    mock_choice = MagicMock()
    mock_choice.message.content = "Answer after rate limit retry"
    mock_choice.message.tool_calls = None
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    mock_completion.usage.prompt_tokens = 50
    mock_completion.usage.completion_tokens = 20
    mock_completion.usage.total_tokens = 70

    # First call raises RateLimitError, second succeeds
    mock_response_err = MagicMock()
    mock_response_err.status_code = 429
    rle = RateLimitError(message="Rate limit exceeded", response=mock_response_err, body=None)

    mock_client.chat.completions.create.side_effect = [rle, mock_completion]
    provider.client = mock_client

    # Speed up sleep in tests
    monkeypatch.setattr("time.sleep", lambda s: None)

    res = provider.generate([LLMMessage(role="user", content="Hello")])
    assert res.content == "Answer after rate limit retry"
    assert mock_client.chat.completions.create.call_count == 2
