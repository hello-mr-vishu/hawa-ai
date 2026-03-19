import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types

from travel_agent.api.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    PlanTripRequest,
    TokenUsageResponse,
    TripRequest,
    TripResponse,
    UserPrefRequest,
    UserPrefResponse,
)
from travel_agent.core.config import settings
from travel_agent.core.logging import get_logger
from travel_agent.core.preferences import (
    build_preference_context,
    get_preferences,
    save_preferences,
)
from travel_agent.core.token_tracker import BudgetExceededError, get_or_create_tracker, get_tracker

logger = get_logger(__name__)

APP_NAME = "hawa-ai"

# Ensure the DB directory exists before ADK tries to open the file
Path(settings.session_db_path).parent.mkdir(parents=True, exist_ok=True)

_session_service: DatabaseSessionService | None = None
_runner: Runner | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _runner, _session_service
    from travel_agent.agent import root_agent  # noqa: PLC0415

    _session_service = DatabaseSessionService(
        db_url=f"sqlite:///{settings.session_db_path}"
    )
    _runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=_session_service,
    )
    logger.info("hawa-ai server started", extra={"extra": {"model": settings.llm_model}})
    yield
    logger.info("hawa-ai server shutting down")


app = FastAPI(
    title="hawa-ai",
    description="Production multi-agent travel planning API",
    version=settings.app_version,
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Ops
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["ops"])
async def health():
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        session_db=settings.session_db_path,
    )


@app.get("/ready", tags=["ops"])
async def ready():
    """Readiness probe — verifies the session DB is accessible."""
    try:
        await _session_service.list_sessions(app_name=APP_NAME, user_id="probe")
        return {"status": "ready"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/session/{session_id}/usage", response_model=TokenUsageResponse, tags=["ops"])
async def get_session_usage(session_id: str):
    tracker = get_tracker(session_id)
    if not tracker:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found or has no token usage recorded.",
        )
    return TokenUsageResponse(
        session_id=session_id,
        total_tokens=tracker.total,
        budget=tracker.budget,
        remaining=max(0, tracker.budget - tracker.total),
        by_agent=tracker.usage_by_agent(),
    )


# ---------------------------------------------------------------------------
# User preferences
# ---------------------------------------------------------------------------

@app.get("/users/{user_id}/preferences", response_model=UserPrefResponse, tags=["users"])
async def get_user_preferences(user_id: str):
    prefs = get_preferences(user_id) or {}
    # Flatten nested lists/None into str values for the generic dict
    flat: dict[str, str] = {}
    for k, v in prefs.items():
        if k == "user_id" or k == "updated_at":
            continue
        if v is None:
            continue
        flat[k] = str(v) if not isinstance(v, list) else ", ".join(v)
    return UserPrefResponse(user_id=user_id, preferences=flat)


@app.put("/users/{user_id}/preferences", response_model=UserPrefResponse, tags=["users"])
async def upsert_user_preference(user_id: str, req: UserPrefRequest):
    existing = get_preferences(user_id) or {}
    # Map generic key/value into the structured preferences dict
    _KEY_MAP = {
        "dietary": "dietary_restrictions",
        "dietary_restrictions": "dietary_restrictions",
        "budget_tier": "budget_tier",
        "home_airport": "home_airport",
        "interests": "interests",
        "preferred_destinations": "preferred_destinations",
        "travel_style": "budget_tier",
        "home_city": "home_airport",
    }
    field = _KEY_MAP.get(req.key, req.key)
    existing[field] = req.value
    save_preferences(user_id, existing)
    return await get_user_preferences(user_id)


@app.delete("/users/{user_id}/preferences/{key}", tags=["users"])
async def delete_user_preference(user_id: str, key: str):
    existing = get_preferences(user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="No preferences found for user.")
    field = key.replace("-", "_")
    if field not in existing:
        raise HTTPException(status_code=404, detail=f"Preference '{key}' not found.")
    existing[field] = None
    save_preferences(user_id, existing)
    return {"deleted": key}


# ---------------------------------------------------------------------------
# Trip planning helpers
# ---------------------------------------------------------------------------

async def _run_agent(user_id: str, session_id: str, message_text: str) -> str:
    """Create or reuse a session and run the agent pipeline. Returns the final response text."""
    tracker = get_or_create_tracker(
        session_id=session_id,
        budget=settings.max_tokens_per_session,
    )

    try:
        await _session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )
    except Exception:
        pass  # session already exists — multi-turn continuation

    message = types.Content(
        role="user",
        parts=[types.Part(text=message_text)],
    )

    response_parts: list[str] = []
    async for event in _runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=message,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    response_parts.append(part.text)

    return "\n\n".join(response_parts) or "No response generated."


# ---------------------------------------------------------------------------
# Trip endpoints
# ---------------------------------------------------------------------------

@app.post("/trip/plan", response_model=TripResponse, tags=["trip"])
async def plan_trip(req: TripRequest):
    """Legacy structured trip planning (Phase 1-compatible)."""
    session_id = req.session_id or str(uuid.uuid4())
    user_id = req.user_id or "anonymous"

    parts = [f"Plan a trip to {req.destination}."]
    if req.query:
        parts.append(req.query)
    if req.dates:
        parts.append(f"Travel dates: {req.dates}.")
    if req.duration_days:
        parts.append(f"Duration: {req.duration_days} days.")
    if req.budget_tier:
        parts.append(f"Budget level: {req.budget_tier}.")
    if req.interests:
        parts.append(f"Interests: {req.interests}.")

    # Inject saved user preferences
    pref_context = build_preference_context(user_id) if user_id != "anonymous" else ""
    query = pref_context + " ".join(parts)

    logger.info(
        "Trip plan request",
        extra={"extra": {"session_id": session_id, "destination": req.destination}},
    )

    try:
        full_response = await _run_agent(user_id, session_id, query)
        tracker = get_tracker(session_id)
        return TripResponse(
            session_id=session_id,
            destination=req.destination,
            response=full_response,
            tokens_used=tracker.total if tracker else None,
        )
    except BudgetExceededError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Trip plan failed", extra={"extra": {"error": str(exc)}})
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/trips/plan", response_model=ChatResponse, tags=["trip"])
async def plan_trip_structured(req: PlanTripRequest):
    """Phase 4: Structured trip planning with user preferences injection and multi-turn support."""
    session_id = req.session_id or str(uuid.uuid4())

    if req.message:
        message_text = req.message
    else:
        parts: list[str] = []
        if req.destination:
            parts.append(f"Plan a trip to {req.destination}.")
        if req.origin_city:
            parts.append(f"Departing from {req.origin_city}.")
        if req.start_date and req.end_date:
            parts.append(f"Travel dates: {req.start_date} to {req.end_date}.")
        if req.interests:
            parts.append(f"Interests: {', '.join(req.interests)}.")
        if req.travel_style:
            parts.append(f"Travel style: {req.travel_style}.")
        if req.dietary:
            parts.append(f"Dietary requirements: {req.dietary}.")
        message_text = " ".join(parts) if parts else "Help me plan a trip."

    # Inject stored user preferences as context prefix
    pref_context = build_preference_context(req.user_id)
    if pref_context:
        message_text = pref_context + message_text

    logger.info(
        "Structured trip plan request",
        extra={"extra": {"session_id": session_id, "user_id": req.user_id}},
    )

    try:
        reply = await _run_agent(req.user_id, session_id, message_text)
        tracker = get_tracker(session_id)
        return ChatResponse(
            session_id=session_id,
            reply=reply,
            tokens_used=tracker.total if tracker else None,
        )
    except BudgetExceededError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Structured trip plan failed", extra={"extra": {"error": str(exc)}})
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/trips/chat", response_model=ChatResponse, tags=["trip"])
async def chat(req: ChatRequest):
    """Multi-turn conversation endpoint. Reuse session_id to continue a conversation."""
    session_id = req.session_id or str(uuid.uuid4())

    # Inject saved preferences on first turn (no session_id provided)
    message_text = req.message
    if not req.session_id:
        pref_context = build_preference_context(req.user_id)
        if pref_context:
            message_text = pref_context + message_text

    logger.info(
        "Chat request",
        extra={"extra": {"session_id": session_id, "user_id": req.user_id}},
    )

    try:
        reply = await _run_agent(req.user_id, session_id, message_text)
        tracker = get_tracker(session_id)
        return ChatResponse(
            session_id=session_id,
            reply=reply,
            tokens_used=tracker.total if tracker else None,
        )
    except BudgetExceededError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Chat failed", extra={"extra": {"error": str(exc)}})
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/trips/sessions/{user_id}", tags=["trip"])
async def list_sessions(user_id: str):
    """List all sessions for a user."""
    try:
        sessions = await _session_service.list_sessions(app_name=APP_NAME, user_id=user_id)
        return {
            "user_id": user_id,
            "sessions": [
                {"session_id": s.id, "last_update_time": s.last_update_time}
                for s in (sessions.sessions if hasattr(sessions, "sessions") else sessions)
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
