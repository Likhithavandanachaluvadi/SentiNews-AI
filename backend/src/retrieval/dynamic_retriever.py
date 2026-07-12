"""
Canonical dynamic retriever module.

The LangGraph implementation currently imports from src.agents.dynamic_retriever.
This wrapper keeps the production architecture path stable for future code while
avoiding a duplicate retriever implementation.
"""
from src.agents.dynamic_retriever import (  # noqa: F401
    FETCH_STRATEGY,
    UI_BLOCKS_MAP,
    dynamic_retriever_node,
    filter_news_results,
    is_finance_relevant_source,
)
