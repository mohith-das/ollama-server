# Ollama Server Middleware

FastAPI middleware that protects Ollama with JWT-based auth, provides token issuance, and proxies requests to the Ollama API.

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
- `POST /generate-token` - exchange password for a JWT
- `POST /protected/{path}` - proxy to Ollama
- `POST /revoke-token`
- `GET /status`

## Notes
- Tokens are stored in memory; restart clears them.
