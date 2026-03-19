from typing import Literal, Optional

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
    user_id: Optional[str] = Field(
        None, description="User ID to load saved preferences for personalized planning"
    )


class PlanTripRequest(BaseModel):
    user_id: str = Field(..., description="User ID (used for preference lookup)")
    session_id: Optional[str] = Field(None, description="Reuse an existing session for multi-turn")
    destination: Optional[str] = Field(None, description="Target destination")
    origin_city: Optional[str] = Field(None, description="Departure city")
    start_date: Optional[str] = Field(None, description="Start date YYYY-MM-DD")
    end_date: Optional[str] = Field(None, description="End date YYYY-MM-DD")
    interests: list[str] = Field(default_factory=list, description="List of interests")
    travel_style: Literal["budget", "mid", "luxury"] = Field(
        "mid", description="Spending level"
    )
    dietary: Optional[str] = Field(None, description="Dietary restrictions")
    message: Optional[str] = Field(None, description="Free-form override message")


class ChatRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    session_id: Optional[str] = Field(None, description="Continue an existing session")
    message: str = Field(..., description="User message")


class UserPreferences(BaseModel):
    preferred_destinations: Optional[list[str]] = Field(
        default=None, description="List of destinations the user wants to visit"
    )
    budget_tier: Optional[str] = Field(
        None, description="Default budget level: budget | mid-range | luxury"
    )
    interests: Optional[list[str]] = Field(
        default=None, description="List of travel interests, e.g. ['food', 'hiking']"
    )
    dietary_restrictions: Optional[str] = Field(None, description="e.g. vegetarian, halal")
    home_airport: Optional[str] = Field(None, description="IATA airport code, e.g. DEL, BOM")


class UserPrefRequest(BaseModel):
    key: str = Field(..., description="Preference key (e.g. dietary, travel_style, home_city)")
    value: str = Field(..., description="Preference value")


class UserPrefResponse(BaseModel):
    user_id: str
    preferences: dict[str, str]


class TripResponse(BaseModel):
    session_id: str
    destination: str
    response: str
    status: str = "success"
    tokens_used: Optional[int] = Field(None, description="Total tokens used in this session so far")


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    tokens_used: Optional[int] = None


class HealthResponse(BaseModel):
    status: str
    version: str
    session_db: str


class TokenUsageResponse(BaseModel):
    session_id: str
    total_tokens: int
    budget: int
    remaining: int
    by_agent: dict[str, int]
