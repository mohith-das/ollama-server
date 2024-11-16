import chromadb.utils.embedding_functions.ollama_embedding_function as ollama_embedding_function
import requests
from typing import Union, cast
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
import httpx
from types import SimpleNamespace
import requests


class OllamaLLMClient:
    def __init__(self, config):
        self.base_url = config["base_url"]
        self.token = None
        self.token_url = f"{self.base_url}/mw/generate-token"
        self.token_password = config.get("token_password", "default_token_password")
        self.headers = {"Content-Type": "application/json"}
        self.model_name = config["model"]

        self.authenticate()

    def authenticate(self):
        payload = {"password": self.token_password}
        response = requests.post(self.token_url, json=payload, headers=self.headers)
        if response.status_code == 200:
            self.token = response.json().get("token")
            self.headers["Authorization"] = f"Bearer {self.token}"
        else:
            raise Exception(f"Authentication failed: {response.text}")

    def create(self, params):
        url = f"{self.base_url}/mw/protected/v1/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": params["messages"],
            "temperature": params.get("temperature", 0.7),
            "max_tokens": params.get("max_tokens", 256),
            "top_p": params.get("top_p", 1.0),
            "frequency_penalty": params.get("frequency_penalty", 0.0),
            "presence_penalty": params.get("presence_penalty", 0.0),
        }
        response_obj = requests.post(url, json=payload, headers=self.headers)
        if response_obj.status_code == 200:
            response_data = response_obj.json()
            # print("Got Content from Ollama:", response_data)

            # Create a custom response object with a cost attribute
            response = SimpleNamespace()
            response.data = response_data
            response.cost = self.cost(
                response_data
            )  # Calculate cost based on response data
            return response
        else:
            raise Exception(f"Error generating response: {response_obj.text}")

    def message_retrieval(self, response):
        # Access the data attribute of the response
        return [choice["message"]["content"] for choice in response.data["choices"]]

    def cost(self, response) -> float:
        # Calculate the cost based on the response
        # Assuming you want to return a fixed cost for now
        return 0  # Return the cost directly instead of trying to set it on the response

    @staticmethod
    def get_usage(content):
        return {}


class OllamaEmbedClient(EmbeddingFunction):
    def __init__(self, config, url, model_name) -> None:
        """
        Initialize the Ollama Embedding Function.

        Args:
            url (str): The URL of the Ollama Server.
            model_name (str): The name of the model to use for text embeddings. E.g. "nomic-embed-text" (see https://ollama.com/library for available models).
        """
        self._api_url = f"{url}"
        self._model_name = model_name
        self._session = httpx.Client(timeout=100.0)
        self.base_url = config["base_url"]
        self.token = None
        self.token_url = f"{self.base_url}/mw/generate-token"
        self.token_password = config.get("token_password", "default_token_password")
        self.headers = {"Content-Type": "application/json"}
        self.model_name = config["model"]
        self.authenticate()

    def authenticate(self):
        payload = {"password": self.token_password}
        response = requests.post(self.token_url, json=payload, headers=self.headers)
        if response.status_code == 200:
            self.token = response.json().get("token")
            self.headers["Authorization"] = f"Bearer {self.token}"
        else:
            raise Exception(f"Authentication failed: {response.text}")

    def __call__(self, input: Union[Documents, str]) -> Embeddings:

        # Call Ollama Server API for each document
        texts = input if isinstance(input, list) else [input]
        print(f"PRINTING TEMP FOR DEBUG {len(texts)}")
        var = self._session.post(
            self._api_url,
            json={"model": self._model_name, "input": texts[0]},
            headers=self.headers,
        )

        var = var.json()["embeddings"]
        print(f"SESSION RESPONSE {var[0]}")
        embeddings = [
            self._session.post(
                self._api_url,
                json={"model": self._model_name, "input": text},
                headers=self.headers,
            ).json()
            for text in texts
        ]
        return cast(
            Embeddings,
            [
                embedding["embeddings"][0]
                for embedding in embeddings
                if "embeddings" in embedding
            ],
        )
