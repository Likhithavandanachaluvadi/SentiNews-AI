from typing import TypedDict, Optional

class ResearchState(TypedDict):
    """
    Represents the state of our financial research graph.
    Enhanced for architectural refinements:
    - Intent classification
    - State propagation tracking
    - Data freshness
    - UI block rendering
    - Comprehensive debugging
    """
    # ===== INPUT =====
    query: str
    ticker: str
    resolved_entities: Optional[dict]
    
    # ===== INTENT CLASSIFICATION =====
    intent: Optional[dict]  # IntentClassification output (primary, secondary, confidence, risk, complexity, etc.)
    
    # ===== RETRIEVAL =====
    context: list[str]
    retrieval_intent: Optional[str]  # Which intent was used for retrieval
    data_freshness: Optional[str]  # Timestamp of data retrieval
    ui_blocks: list[str]  # UI blocks to render based on intent
    
    # ===== ANALYST REPORTS (PRESERVED - never overwrite with null) =====
    fundamental_report: Optional[dict]
    technical_report: Optional[dict]
    sentiment_report: Optional[dict]
    
    # ===== VERIFICATION =====
    reflection_feedback: Optional[dict]
    iteration_count: int
    
    # ===== SYNTHESIS =====
    final_report: Optional[dict]
    
    # ===== DEBUGGING =====
    execution_logs: Optional[list[dict]]  # Debug logs from debug_logger

    news_articles: list[dict]

    # ===== GROUNDING LAYER =====
    grounding_data: Optional[dict]
    prompt_context: Optional[str]