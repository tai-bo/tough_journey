# Performance Review API

This is the backend for an app that helps people write their performance reviews. Users record short voice notes about their work through the year. The service transcribes each note, stores it so it can be searched by meaning, and groups related notes into themes. Those themes become the raw material for a review.

Built with Python and FastAPI, running on Google Cloud Run.

## Endpoints

| Endpoint | What it does |
|---|---|
| `POST /save_transcription` | Takes a recording in Cloud Storage, transcribes it, and saves it to Qdrant, Cloud Storage and Firestore |
| `POST /group_transcription` | Groups a user's notes (optionally within a date range) into themes |
| `GET /health` | Health check |

## Key strengths

- **System design:** a clean, layered codebase, with Qdrant collections and queries defined in config files rather than hard-coded.
- **Reliability:** a Redis lock and a Firestore "processed" check stop the same recording being processed twice. The AI models fall back from Gemini to an OpenAI-compatible model if one fails.
- **Applied AI:** speech-to-text, summaries and embeddings with pydantic-ai. Notes are grouped by linking each one to its most similar notes and running Louvain community detection on the resulting graph.
- **Cloud and DevOps:** Docker builds deployed through GitHub Actions to separate dev, test and production Google Cloud projects. Secrets are kept in Secret Manager, and Logfire records what each request does.
- **Engineering habits:** typed models throughout (Pydantic v2), pytest tests run by a GitHub Actions workflow and Docker Compose, and pull-request-based work across environment branches.

## Tech stack

Python 3.13 · FastAPI · Pydantic v2 · pydantic-ai · Qdrant · Firestore · Cloud Storage · Redis · networkx · Logfire · Docker · GitHub Actions · Cloud Run · uv

## Status

Journey ended.
