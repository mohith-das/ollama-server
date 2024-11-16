import os
from datetime import datetime, timedelta
import httpx
from fastapi import FastAPI, HTTPException, Request

# Configuration
BASE_URL = os.getenv("BASE_URL", "http://144.24.112.144/amp/mw")  # Middleware URL
PASSWORD = os.getenv("TOKEN_PASSWORD", "default_token_password")  # Token password
API_KEY = os.getenv("API_KEY", "ollama")  # Default API key

# Initialize FastAPI app
app = FastAPI()

# In-memory token storage
auth_token = None
token_expiry = None


async def get_new_token():
    """Fetch a new token from the middleware."""
    global auth_token, token_expiry
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/generate-token", json={"password": PASSWORD}
            )
            response.raise_for_status()
            data = response.json()
            auth_token = data["token"]
            token_expiry = datetime.utcnow() + timedelta(hours=4)  # Match token expiry
            return auth_token
    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"Failed to get new token: {e}")


async def get_token():
    """Ensure a valid token is available."""
    global auth_token, token_expiry
    if auth_token is None or datetime.utcnow() >= token_expiry:
        await get_new_token()
    return auth_token


@app.middleware("http")
async def validate_api_key_and_token_middleware(request: Request, call_next):
    """
    Middleware to validate API key and ensure token validity for each request.
    """
    api_key = request.headers.get("x-api-key")
    if api_key != API_KEY and api_key != "":
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    # Ensure token is valid
    await get_token()

    # Proceed to the next middleware or endpoint
    response = await call_next(request)
    return response


@app.api_route("/pxy/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_request(path: str, request: Request):
    """
    Pass requests through the protected route.
    """
    token = await get_token()

    # Construct the full URL for the protected route
    protected_url = f"{BASE_URL}/protected/{path}"

    # Forward the original method, headers, and body
    async with httpx.AsyncClient() as client:
        try:
            method = request.method.upper()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": request.headers.get("Content-Type", "application/json"),
            }

            if method == "GET":
                response = await client.get(
                    protected_url, headers=headers, params=request.query_params
                )
            elif method in {"POST", "PUT", "PATCH"}:
                body = await request.body()
                response = await client.request(
                    method, protected_url, headers=headers, content=body
                )
            elif method == "DELETE":
                response = await client.delete(protected_url, headers=headers)
            else:
                raise HTTPException(status_code=405, detail="Method not allowed")

            return {
                "status_code": response.status_code,
                "content": response.json(),
                "headers": dict(response.headers),
            }
        except httpx.HTTPError as e:
            raise HTTPException(status_code=500, detail=f"Failed to proxy request: {e}")


@app.get("/mw/")
async def root():
    """Simple status check."""
    return {"message": "Proxy is running and ready to handle requests"}


# Run the application on port 11434
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("proxy_script:app", host="0.0.0.0", port=11434, reload=True)

# uvicorn ollama_proxy_client:app --host 0.0.0.0 --port 11434 --reload
