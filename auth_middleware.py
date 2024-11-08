from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta
from starlette.responses import StreamingResponse
import jwt
import requests
import os
import logging

# Logging setup
logging.basicConfig(level=logging.INFO)

# Initialize FastAPI app
app = FastAPI()

# Secret key for encoding/decoding tokens
SECRET_KEY = os.getenv("SECRET_KEY", "default_secret_key")
ALGORITHM = "HS256"

# Token Expiry in hours
TOKEN_EXPIRE_HOURS = int(os.getenv("TOKEN_EXPIRE_HOURS", "4"))

# Password for token generation
TOKEN_PASSWORD = os.getenv("TOKEN_PASSWORD", "default_token_password")

# Ollama API URL
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://127.0.0.1:11434/")

# In-memory token store
tokens = {}

# Security schema
security = HTTPBearer()


# Function to generate a token
def generate_token():
    expiry_time = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    logging.info(f"Token expiry time: {expiry_time.isoformat()}")
    payload = {
        "exp": expiry_time,  # Change this to datetime object instead of timestamp
        "iat": datetime.utcnow(),  # Change this to datetime object instead of timestamp
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    tokens[token] = expiry_time  # Store token with its expiry time
    return token


# Function to verify a token
def verify_token(token: str):
    logging.info(f"Current time: {datetime.utcnow().isoformat()}")
    logging.info(f"Stored tokens: {tokens}")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        logging.info(f"Token payload: {payload}")

        # Check if token is in memory and not expired
        if token not in tokens:
            logging.warning("Token not found in memory")
            raise HTTPException(status_code=403, detail="Token invalid or not found")

        expiry_time = tokens[token]
        if datetime.utcnow() > expiry_time:
            logging.warning("Token has expired")
            del tokens[token]  # Clean up expired token
            raise HTTPException(status_code=403, detail="Token expired")

        return payload  # Valid token
    except jwt.ExpiredSignatureError:
        logging.warning("JWT library flagged token as expired")
        if token in tokens:
            del tokens[token]  # Clean up expired token
        raise HTTPException(status_code=403, detail="Token expired")
    except jwt.InvalidTokenError as e:
        logging.error(f"Invalid token: {str(e)}")
        raise HTTPException(status_code=403, detail=f"Invalid token: {str(e)}")


# Middleware to enforce token authentication
async def auth_middleware(request: Request, call_next):
    # Allow unauthenticated access only to these routes
    unauthenticated_routes = ["/generate-token", "/"]

    if request.url.path not in unauthenticated_routes:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid token")

        token = auth_header.split(" ")[1]
        verify_token(token)  # Validate the token

    return await call_next(request)  # Proceed to the next middleware or endpoint


# Add the middleware to the app
app.middleware("http")(auth_middleware)


# Endpoint to generate a token (password-protected)
@app.post("/generate-token")
async def create_token(request: Request):
    data = await request.json()
    password = data.get("password")
    if not password:
        raise HTTPException(status_code=400, detail="Password is required")
    if password != TOKEN_PASSWORD:
        raise HTTPException(status_code=403, detail="Invalid password")

    token = generate_token()
    return {"token": token}


# Protected route for pass-through with streaming
@app.post("/protected/{path:path}")
async def protected_route(
    path: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    # Token verification
    verify_token(credentials.credentials)

    try:
        # Construct the full Ollama URL including any subpath
        ollama_url = f"{OLLAMA_API_URL.rstrip('/')}/{path}"

        # Get the raw request body
        body = await request.body()
        headers = {
            "Content-Type": request.headers.get("Content-Type", "application/json")
        }

        # Pass the request to Ollama, maintaining streaming if specified
        response = requests.post(ollama_url, data=body, headers=headers, stream=True)

        # Check for errors
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Ollama API Error: {response.text}",
            )

        # Stream the response back
        return StreamingResponse(
            response.iter_content(chunk_size=1024),
            media_type=response.headers.get("Content-Type", "application/json"),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query Ollama: {str(e)}")


# Endpoint to revoke a token
@app.post("/revoke-token")
async def revoke_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    if token in tokens:
        del tokens[token]
        return {"message": "Token revoked successfully"}
    else:
        raise HTTPException(status_code=404, detail="Token not found")


# Status endpoint to check middleware and Ollama status
@app.get("/status")
def status(credentials: HTTPAuthorizationCredentials = Depends(security)):
    verify_token(credentials.credentials)  # Verify token for /status
    # Middleware ensures this is only accessible with a valid token
    middleware_status = "running"

    try:
        response = requests.get("http://127.0.0.1:11434/")
        ollama_status = "running" if response.status_code == 200 else "not running"
    except Exception:
        ollama_status = "not reachable"

    return {"middleware_status": middleware_status, "ollama_status": ollama_status}


# Example root endpoint
@app.get("/")
def root():
    return {"message": "Welcome to the Authenticated API"}
