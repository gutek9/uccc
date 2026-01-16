from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CostEntryBase(BaseModel):
    date: date
    provider: str
    account_id: str
    account_name: Optional[str] = None
    service: str
    region: Optional[str] = None
    cost: float
    currency: str
    tags: Optional[Dict[str, Any]] = None


class CostEntryCreate(CostEntryBase):
    id: str


class CostEntryRead(CostEntryBase):
    id: str
    created_at: Optional[str] = None


class TotalCostResponse(BaseModel):
    total_cost: float
    currency: Optional[str] = None


class GroupedCostResponse(BaseModel):
    key: str
    total_cost: float


class AnomalyResponse(BaseModel):
    provider: str
    date: date
    total_cost: float
    previous_day_cost: Optional[float] = None
    delta_ratio: Optional[float] = None


class ProviderBreakdownResponse(BaseModel):
    provider: str
    total_cost: float
    services: List[GroupedCostResponse]
    accounts: List[GroupedCostResponse]


class ProviderTotalResponse(BaseModel):
    provider: str
    total_cost: float
    currency: str


class DeltaGroupResponse(BaseModel):
    key: str
    current_cost: float
    previous_cost: float
    delta: float
    delta_ratio: Optional[float] = None


class SignalResponse(BaseModel):
    severity: str
    provider: str
    entity_type: str
    entity_id: str
    impact_cost: float
    impact_pct: Optional[float] = None
    date: date


class TagCoverageResponse(BaseModel):
    required_tags: List[str]
    total_cost: float
    fully_tagged_cost: float
    partially_tagged_cost: float
    untagged_cost: float


class TagCoverageByProviderResponse(BaseModel):
    provider: str
    coverage: TagCoverageResponse


class UntaggedCostEntry(BaseModel):
    id: str
    date: date
    provider: str
    account_id: str
    service: str
    region: Optional[str]
    cost: float
    currency: str
    missing_tags: List[str] = Field(default_factory=list)


class TagHygieneResponse(BaseModel):
    coverage: TagCoverageResponse
    untagged_entries: List[UntaggedCostEntry]


class DataFreshnessResponse(BaseModel):
    provider: str
    last_entry_date: Optional[date] = None
    last_ingested_at: Optional[str] = None
    lookback_days: Optional[int] = None
