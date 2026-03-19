# hawa-ai — Production Multi-Agent Travel Planner

A production-ready travel planning API built on [Google ADK](https://github.com/google/adk-python) using a multi-agent pipeline.

## Architecture

```
POST /trips/plan  ──► trip_planner_pipeline (SequentialAgent)
                          │
                          ├─► travel_inspiration_agent  (destination + news + places)
                          │       ├─► news_agent         (Google Search)
                          │       └─► places_agent       (OpenStreetMap / Overpass)
                          │
                          ├─► weather_agent              (climate & packing guide)
                          ├─► itinerary_agent            (day-by-day plan)
                          └─► budget_agent               (cost breakdown table)
```

All agents share session history via ADK's `SqliteSessionService`, enabling multi-turn conversation.

## Quickstart

```bash
# 1. Clone and install
git clone <repo-url>
cd hawa-ai
uv sync

# 2. Set environment variables
cp .env.example .env   # add your GOOGLE_API_KEY

# 3. Run
uv run uvicorn travel_agent.api.server:app --port 8000 --reload
```

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/ready` | Readiness probe (checks DB) |
| POST | `/trips/plan` | Structured trip planning with preferences |
| POST | `/trips/chat` | Multi-turn chat (reuse `session_id`) |
| POST | `/trip/plan` | Legacy trip planning endpoint |
| GET | `/trips/sessions/{user_id}` | List sessions for a user |
| GET | `/session/{session_id}/usage` | Token usage breakdown by agent |
| GET | `/users/{user_id}/preferences` | Get saved user preferences |
| PUT | `/users/{user_id}/preferences` | Set a user preference |
| DELETE | `/users/{user_id}/preferences/{key}` | Delete a user preference |

### Example: Plan a trip

```bash
curl -X POST http://localhost:8000/trips/plan \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "alice",
    "destination": "Kyoto",
    "start_date": "2026-10-01",
    "end_date": "2026-10-08",
    "interests": ["temples", "food"],
    "travel_style": "mid"
  }'
```

### Example: Multi-turn conversation

```bash
# First turn — get session_id from response
SESSION=$(curl -s -X POST http://localhost:8000/trips/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"alice","message":"Plan a 5-day trip to Tokyo."}' | jq -r .session_id)

# Follow-up turn
curl -X POST http://localhost:8000/trips/chat \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":\"alice\",\"session_id\":\"$SESSION\",\"message\":\"Change day 3 to include more shopping.\"}"
```

### Example: Save preferences

```bash
curl -X PUT http://localhost:8000/users/alice/preferences \
  -H "Content-Type: application/json" \
  -d '{"key":"dietary","value":"vegetarian"}'
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_API_KEY` | — | Required. Gemini API key |
| `GOOGLE_GENAI_USE_VERTEXAI` | `0` | Use Vertex AI instead of API key |
| `LLM_MODEL` | `gemini-2.5-flash-lite` | Model name |
| `MAX_TOKENS_PER_SESSION` | `50000` | Token budget per session |
| `SESSION_DB_PATH` | `travel_agent/.adk/session.db` | SQLite database path |
| `LOG_FORMAT` | `json` | `json` or `text` |
| `APP_VERSION` | `1.0.0` | Reported in `/health` |

## Docker Deployment

```bash
# Build and start
GOOGLE_API_KEY=your_key docker compose up --build

# Health check
curl http://localhost:8000/health

# Restart with persistent sessions
docker compose down && docker compose up
```

Sessions and user preferences are persisted in the `travel_data` Docker volume. Sessions survive container restarts.

## Running Tests

```bash
# Unit tests (no API key required)
uv run pytest tests/unit/ -v

# With coverage
uv run pytest tests/unit/ --cov=travel_agent --cov-report=term

# Integration tests (requires GOOGLE_API_KEY)
GOOGLE_API_KEY=your_key uv run pytest tests/integration/ -v
```
