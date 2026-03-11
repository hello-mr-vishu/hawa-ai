import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from travel_agent.api.schemas import HealthResponse, TripRequest, TripResponse
from travel_agent.core.config import settings
from travel_agent.core.logging import get_logger

logger = get_logger(__name__)

APP_NAME = "hawa-ai"

# Shared session service (in-memory for dev; swap for DatabaseSessionService in prod)
_session_service = InMemorySessionService()
_runner: Runner | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _runner
    # Lazy import to avoid circular imports at module load
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

    logger.info(
        "Trip plan request",
        extra={"extra": {"session_id": session_id, "destination": req.destination}},
    )

    try:
        # Ensure session exists (idempotent)
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
            extra={"extra": {"session_id": session_id, "response_len": len(full_response)}},
        )
        return TripResponse(
            session_id=session_id,
            destination=req.destination,
            response=full_response,
        )

    except Exception as exc:
        logger.error(
            "Trip plan failed",
            extra={"extra": {"session_id": session_id, "error": str(exc)}},
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc
