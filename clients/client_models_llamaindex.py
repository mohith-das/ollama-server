from pydantic import Field, BaseModel, ConfigDict
from llama_index.core.llms import (
    CustomLLM,
    CompletionResponse,
    CompletionResponseGen,
    LLMMetadata,
)
from llama_index.core.embeddings import BaseEmbedding
from llama_index.core.llms.callbacks import llm_completion_callback
from typing import List, Any, Optional
import requests
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class OurLLM(CustomLLM):
    base_url: str = Field(default=None)
    token_url: str = Field(default=None)
    token_password: str = Field(default="default_token_password")
    headers: dict = Field(default_factory=lambda: {"Content-Type": "application/json"})
    llm_model_name: str = Field(default=None)
    context_window: int = Field(default=3900)
    num_output: int = Field(default=256)
    token: Optional[str] = Field(default=None)

    model_config = ConfigDict(protected_namespaces=())

    def __init__(self, config: dict):
        super().__init__()
        self.base_url = config["base_url"]
        self.token_url = f"{self.base_url}/mw/generate-token"
        self.token_password = config.get("token_password", "default_token_password")
        self.headers = {"Content-Type": "application/json"}
        self.llm_model_name = config["model"]
        self.context_window = config.get("context_window", 3900)
        self.num_output = config.get("num_output", 256)
        self.authenticate()

    def authenticate(self):
        logger.info("Authenticating LLM...")
        payload = {"password": self.token_password}
        response = requests.post(self.token_url, json=payload, headers=self.headers)
        if response.status_code == 200:
            self.token = response.json().get("token")
            self.headers["Authorization"] = f"Bearer {self.token}"
            logger.info("Authentication successful.")
        else:
            logger.error(f"Authentication failed: {response.text}")
            raise Exception(f"Authentication failed: {response.text}")

    @property
    def metadata(self) -> LLMMetadata:
        return LLMMetadata(
            context_window=self.context_window,
            num_output=self.num_output,
            model_name=self.llm_model_name,
        )

    @llm_completion_callback()
    def complete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        logger.info(f"Sending completion request for prompt: {prompt[:50]}...")
        url = f"{self.base_url}/mw/protected/v1/chat/completions"
        payload = {
            "model": self.llm_model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": self.num_output,
            "stream": False,
        }
        response = requests.post(url, json=payload, headers=self.headers)
        if response.status_code == 200:
            content = response.json()["choices"][0]["message"]["content"]
            logger.info("Completion request successful.")
            return CompletionResponse(text=content)
        else:
            logger.error(f"Error generating response: {response.text}")
            raise Exception(f"Error generating response: {response.text}")

    @llm_completion_callback()
    def stream_complete(self, prompt: str, **kwargs: Any) -> CompletionResponseGen:
        logger.info(f"Streaming completion request for prompt: {prompt[:50]}...")
        url = f"{self.base_url}/mw/protected/v1/chat/completions"
        payload = {
            "model": self.llm_model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": self.num_output,
            "stream": True,
        }
        with requests.post(
            url, json=payload, headers=self.headers, stream=True
        ) as response:
            if response.status_code == 200:
                response_text = ""
                for line in response.iter_lines():
                    if line:
                        token = line.decode("utf-8")
                        response_text += token
                        yield CompletionResponse(text=response_text, delta=token)
            else:
                logger.error(f"Error streaming response: {response.text}")
                raise Exception(f"Error streaming response: {response.text}")


# Define Custom Embeddings
class OllamaEmbeddings(BaseEmbedding, BaseModel):
    base_url: str = Field(..., description="The base URL for the Ollama API")
    token_password: str = Field(..., description="Password to generate API token")
    embed_model: str = Field(..., description="Embedding model name")
    token: str = Field(default=None, description="Generated API token")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.token = self._generate_token()

    def _generate_token(self) -> str:
        logger.info("Generating API token...")
        url = f"{self.base_url}/mw/generate-token"
        payload = {"password": self.token_password}
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            logger.info("Token generation successful.")
            return response.json().get("token")
        else:
            logger.error(f"Error generating token: {response.text}")
            raise Exception(f"Error generating token: {response.text}")

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def _get_embedding(self, text: str) -> List[float]:
        logger.info(f"Fetching embedding for text: {text[:50]}...")
        url = f"{self.base_url}/mw/protected/api/embed"
        payload = {"model": self.embed_model, "input": text}
        response = requests.post(url, json=payload, headers=self._get_headers())
        response.raise_for_status()
        embeddings = response.json().get("embeddings", [[]])
        logger.info("Embedding fetched successfully.")
        return embeddings[0] if embeddings else []

    def _get_query_embedding(self, query: str) -> List[float]:
        return self._get_embedding(query)

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._get_embedding(text)

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        return [self._get_embedding(text) for text in texts]

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return self._get_query_embedding(query)

    async def _aget_text_embedding(self, text: str) -> List[float]:
        return self._get_text_embedding(text)
