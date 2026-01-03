# Ollama Server Middleware

JWT-protected FastAPI proxy for Ollama with token issuance and request forwarding.

## Highlights
- Password-protected token creation with expiry.
- Bearer auth enforced on proxy routes.
- Streams Ollama responses through a protected endpoint.

## Tech
Python, FastAPI, JWT, Ollama

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration
Set environment variables as needed:
- `SECRET_KEY` (default: `default_secret_key`)
- `TOKEN_PASSWORD` (default: `default_token_password`)
- `TOKEN_EXPIRE_HOURS` (default: `4`)
- `OLLAMA_API_URL` (default: `http://127.0.0.1:11434/`)

## Run
```bash
uvicorn auth_middleware:app --host 0.0.0.0 --port 8000
```

## Endpoints
- `POST /generate-token`
- `POST /protected/{path}`
- `POST /revoke-token`
- `GET /status`
