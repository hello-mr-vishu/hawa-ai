FROM python:3.13-slim

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy application code
COPY . .

# Create persistent data directory for SQLite DB
RUN mkdir -p /app/data

ENV SESSION_DB_PATH=/app/data/session.db
ENV LOG_FORMAT=json
ENV HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "travel_agent.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
