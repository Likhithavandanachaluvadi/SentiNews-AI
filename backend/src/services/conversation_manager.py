import time
from typing import Dict, Any, List, Optional, Literal
import uuid
import logging
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from src.core.config import settings

logger = logging.getLogger(__name__)

class QueryIntentResolution(BaseModel):
    intent: Literal["NEW_CONVERSATION", "FOLLOW_UP", "COMPARE", "CLARIFICATION", "GENERAL_QUESTION"]
    resolved_query: str = Field(description="The contextual expanded query combining past summary, history, and the current question.")
    resolved_ticker: Optional[str] = Field(None, description="The resolved ticker symbol. Return a new ticker if compared or asked, otherwise previous ticker.")
    resolved_entities: Optional[dict] = Field(None, description="The resolved EntityCollection serialized to dict.")

class Conversation:
    def __init__(self, conversation_id: str, ticker: Optional[str] = None):
        self.conversation_id = conversation_id
        self._ticker = ticker
        self.resolved_entities = None
        self.messages: List[Dict[str, str]] = []  # List of {"role": "user" or "assistant", "content": "..."}
        self.previous_intent: Optional[str] = None
        self.last_summary: Optional[str] = None
        self.last_active = time.time()

    @property
    def ticker(self) -> Optional[str]:
        if self.resolved_entities and not self.resolved_entities.is_empty:
            return self.resolved_entities.primary_ticker
        return self._ticker

    @ticker.setter
    def ticker(self, val: Optional[str]):
        self._ticker = val

    def update_activity(self):
        self.last_active = time.time()

    def is_expired(self, expiry_seconds: float = 1800.0) -> bool:
        return (time.time() - self.last_active) > expiry_seconds

class ConversationManager:
    def __init__(self):
        self._store: Dict[str, Conversation] = {}
        self.expiry_seconds = 1800.0  # 30 minutes in seconds

    def get_or_create_conversation(self, conversation_id: Optional[str] = None) -> Conversation:
        self.cleanup_expired()
        
        # If conversation_id is missing or not in store, create a new one
        if not conversation_id or conversation_id not in self._store:
            new_id = str(uuid.uuid4())
            conversation = Conversation(new_id)
            self._store[new_id] = conversation
        else:
            conversation = self._store[conversation_id]
            conversation.update_activity()
            
        return conversation

    def save_message(
        self, 
        conversation_id: str, 
        role: str, 
        content: str, 
        ticker: Optional[str] = None, 
        intent: Optional[str] = None, 
        last_summary: Optional[str] = None,
        resolved_entities: Optional[dict] = None
    ):
        conversation = self.get_or_create_conversation(conversation_id)
        conversation.messages.append({"role": role, "content": content})
        if resolved_entities:
            from src.services.entity_models import EntityCollection
            conversation.resolved_entities = EntityCollection.from_dict(resolved_entities)
        elif ticker:
            conversation.ticker = ticker
        if intent:
            conversation.previous_intent = intent
        if last_summary:
            conversation.last_summary = last_summary
        conversation.update_activity()

    async def resolve_query_intent(self, conversation_id: str, query: str) -> QueryIntentResolution:
        conversation = self.get_or_create_conversation(conversation_id)
        
        # If no history, it's a NEW_CONVERSATION
        if not conversation.messages:
            from src.services.entity_resolution_pipeline import EntityResolutionPipeline
            collection = await EntityResolutionPipeline.resolve_entities(query)
            conversation.resolved_entities = collection
            return QueryIntentResolution(
                intent="NEW_CONVERSATION",
                resolved_query=query,
                resolved_ticker=collection.primary_ticker,
                resolved_entities=collection.to_dict()
            )
            
        try:
            # Build previous history context
            prev_history = ""
            for msg in conversation.messages[-6:]:  # Last 3 turns
                prev_history += f"{msg['role'].capitalize()}: {msg['content']}\n"
                
            prev_ticker = conversation.ticker or "None"
            prev_summary = conversation.last_summary or "None"
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an Intelligent Conversational Router.
Your job is to analyze the user's current question, the previous ticker, the previous summary, and the recent conversation history.

Determine:
1. The intent:
   - NEW_CONVERSATION: Starting a brand new topic or analyzing a new company not related to the current discussion.
   - FOLLOW_UP: Asking details, risks, or deep-dives about the active company (e.g., "Why?", "What are the risks?", "Explain CUDA", "Would you invest?").
   - COMPARE: Requesting comparison of the active company with another peer (e.g., "Compare with AMD", "Compare with TCS").
   - CLARIFICATION: Asking to explain a term or a metric mentioned in the previous summary (e.g. "What is PE ratio?", "What do you mean by CUDA?").
   - GENERAL_QUESTION: Broad finance questions not specific to a company.

2. The resolved_query:
   - Expand context-dependent questions to be fully self-contained.
   - Example 1: Current question is "Why?", previous ticker is "NVDA", previous summary is "NVIDIA is showing robust growth in AI chips". Expand resolved_query to "Why is NVIDIA showing robust growth in AI chips?".
   - Example 2: Current question is "Compare with AMD", previous ticker is "NVDA". Expand resolved_query to "Compare NVIDIA with AMD".
   - Example 3: Current question is "What are the risks?", previous ticker is "NVDA". Expand resolved_query to "What are the investment risks of NVIDIA?".

3. The resolved_ticker:
   - If user asks about a new company/ticker directly or in comparison (e.g. "Compare with AMD" or "How about Infosys?"), output that new ticker symbol (e.g. "AMD" or "INFY").
   - Otherwise, fallback to the previous ticker.

You must format your response as a valid JSON object matching the QueryIntentResolution schema.
Example JSON:
{{
  "intent": "FOLLOW_UP",
  "resolved_query": "Why is NVIDIA showing robust growth in AI chips?",
  "resolved_ticker": "NVDA"
}}"""),
                ("user", "Previous Ticker: {prev_ticker}\nPrevious Summary: {prev_summary}\nPrevious History:\n{prev_history}\n\nCurrent Question: {query}")
            ])
            
            llm = ChatGroq(
                temperature=0.0,
                model_name="llama-3.1-8b-instant",
                api_key=settings.GROQ_API_KEY
            )
            structured_llm = llm.with_structured_output(QueryIntentResolution, method="json_mode")
            chain = prompt | structured_llm
            
            result: QueryIntentResolution = await chain.ainvoke({
                "prev_ticker": prev_ticker,
                "prev_summary": prev_summary,
                "prev_history": prev_history.strip(),
                "query": query,
            })
            
            # Resolve entities for the new query
            from src.services.entity_resolution_pipeline import EntityResolutionPipeline
            collection = EntityResolutionPipeline.resolve_entities_sync(result.resolved_query or query)
            
            # If no entities resolved in the new query but it's a follow-up/clarification,
            # we inherit the previous conversation's entities!
            if collection.is_empty and result.intent in ("FOLLOW_UP", "CLARIFICATION") and conversation.resolved_entities:
                collection = conversation.resolved_entities
                
            result.resolved_entities = collection.to_dict()
            result.resolved_ticker = collection.primary_ticker or result.resolved_ticker
            
            # Store in conversation state
            conversation.resolved_entities = collection
            
            if not result.resolved_ticker or result.resolved_ticker.upper() in ("NONE", "N/A", "NULL"):
                result.resolved_ticker = conversation.ticker
                
            logger.info(f"Resolved intent classification: {result.intent}, ticker: {result.resolved_ticker}, query: {result.resolved_query}")
            return result
            
        except Exception as e:
            logger.warning(f"Failed to resolve intent classification: {e}. Fallback to NEW_CONVERSATION.")
            # Fallback resolver collection
            from src.services.entity_resolution_pipeline import EntityResolutionPipeline
            collection = EntityResolutionPipeline.resolve_entities_sync(query)
            if collection.is_empty and conversation.resolved_entities:
                collection = conversation.resolved_entities
            return QueryIntentResolution(
                intent="NEW_CONVERSATION",
                resolved_query=query,
                resolved_ticker=collection.primary_ticker or conversation.ticker,
                resolved_entities=collection.to_dict()
            )

    def cleanup_expired(self):
        now = time.time()
        expired_ids = [cid for cid, conv in self._store.items() if conv.is_expired(self.expiry_seconds)]
        for cid in expired_ids:
            del self._store[cid]

# Global singleton instance
conversation_manager = ConversationManager()
