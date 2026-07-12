from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class ResolvedEntity(BaseModel):
    ticker: str
    company_name: str
    exchange: str = "NSE"
    country: str = "IN"
    confidence: float
    resolution_source: str
    aliases: List[str] = Field(default_factory=list)
    is_primary: bool = False
    query_span: str = ""

class EntityCollection(BaseModel):
    entities: List[ResolvedEntity] = Field(default_factory=list)
    query: str
    resolution_mode: str
    total_found: int
    resolution_warnings: List[str] = Field(default_factory=list)
    resolved_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    @property
    def primary(self) -> Optional[ResolvedEntity]:
        return self.entities[0] if self.entities else None

    @property
    def primary_ticker(self) -> Optional[str]:
        return self.entities[0].ticker if self.entities else None

    @property
    def all_tickers(self) -> List[str]:
        return [e.ticker for e in self.entities]

    @property
    def is_empty(self) -> bool:
        return len(self.entities) == 0

    @property
    def is_single(self) -> bool:
        return len(self.entities) == 1

    @property
    def is_multi(self) -> bool:
        return len(self.entities) > 1

    def to_dict(self) -> dict:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "EntityCollection":
        if not data:
            return cls(entities=[], query="", resolution_mode="EDUCATIONAL", total_found=0)
        return cls(**data)

    def get_entity(self, ticker: str) -> Optional[ResolvedEntity]:
        ticker_upper = ticker.upper().strip()
        for e in self.entities:
            if e.ticker.upper().strip() == ticker_upper:
                return e
        return None
