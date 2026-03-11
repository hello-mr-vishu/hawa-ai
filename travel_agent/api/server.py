import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from travel_agent.api.schemas import (
    HealthResponse,
    TokenUsageResponse,
    TripRequest,
    TripResponse,
)
from travel_agent.core.config import settings
from travel_agent.core.logging import get_logger
from travel_agent.core.token_tracker import BudgetExceededError, get_or_create_tracker, get_tracker

logger = get_logger(__name__)

APP_NAME = "hawa-ai"

_session_service = InMemorySessionService()
_runner: Runner | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _runner
    from travel_agent.agent import root_agent  # noqa: PLC0415

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


@app.get("/health", response_model=HealthResponse, tags=["ops"])
async def health():
    return HealthResponse(status="ok", version=settings.app_version)


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


@app.post("/trip/plan", response_model=TripResponse, tags=["trip"])
async def plan_trip(req: TripRequest):
    session_id = req.session_id or str(uuid.uuid4())
    user_id = "anonymous"

    # Build the query string from request fields
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
    query = " ".join(parts)

    # Register a token tracker for this session (idempotent)
    tracker = get_or_create_tracker(
        session_id=session_id,
        budget=settings.max_tokens_per_session,
    )

    logger.info(
        "Trip plan request",
        extra={"extra": {"session_id": session_id, "destination": req.destination}},
    )

    try:
        try:
            _session_service.create_session(
                app_name=APP_NAME,
                user_id=user_id,
                session_id=session_id,
            )
        except Exception:
            pass  # session already exists

        message = types.Content(
            role="user",
            parts=[types.Part(text=query)],
        )

        response_parts: list[str] = []
        for event in _runner.run(
            user_id=user_id,
            session_id=session_id,
            new_message=message,
        ):
            if event.is_final_response() and event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        response_parts.append(part.text)

        full_response = "\n\n".join(response_parts) or "No response generated."
        logger.info(
            "Trip plan complete",
            extra={
                "extra": {
                    "session_id": session_id,
                    "response_len": len(full_response),
                    "tokens_used": tracker.total,
                }
            },
        )
        return TripResponse(
            session_id=session_id,
            destination=req.destination,
            response=full_response,
            tokens_used=tracker.total,
        )

    except BudgetExceededError as exc:
        logger.warning(
            "Token budget exceeded",
            extra={"extra": {"session_id": session_id, "tokens_used": tracker.total}},
        )
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(
            "Trip plan failed",
            extra={"extra": {"session_id": session_id, "error": str(exc)}},
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc
