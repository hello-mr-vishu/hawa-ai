from typing import Optional

from pydantic import BaseModel, Field


class TripRequest(BaseModel):
    destination: str = Field(..., description="Travel destination (city, country, or region)")
    query: Optional[str] = Field(None, description="Free-form travel query or intent")
    dates: Optional[str] = Field(None, description="Travel dates, e.g. 'April 2025'")
    duration_days: Optional[int] = Field(None, description="Number of travel days", ge=1, le=90)
    budget_tier: Optional[str] = Field(
        None, description="Budget level: budget | mid-range | luxury"
    )
    interests: Optional[str] = Field(
        None, description="Comma-separated interests, e.g. 'food, hiking'"
    )
    session_id: Optional[str] = Field(
        None, description="Session ID for token tracking (auto-generated if omitted)"
    )


class TripResponse(BaseModel):
    session_id: str
    destination: str
    response: str
    status: str = "success"
    tokens_used: Optional[int] = Field(None, description="Total tokens used in this session so far")


class HealthResponse(BaseModel):
    status: str
    version: str


class TokenUsageResponse(BaseModel):
    session_id: str
    total_tokens: int
    budget: int
    remaining: int
    by_agent: dict[str, int]
