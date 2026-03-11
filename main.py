import uvicorn

from travel_agent.core.config import settings
from travel_agent.core.logging import get_logger

logger = get_logger(__name__)


def main():
    logger.info("Starting hawa-ai server", extra={"extra": {"version": settings.app_version}})
    uvicorn.run(
        "travel_agent.api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="warning",  # suppress uvicorn default logs; app uses JSON logger
    )


if __name__ == "__main__":
    main()
