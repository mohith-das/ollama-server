from types import SimpleNamespace
import requests
import json
from autogen import ConversableAgent


class OllamaClient:
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


model_config = {
    "model": "llama3.2:latest",
    "model_client_cls": "OllamaClient",
    "base_url": "http://144.24.112.144",
    "token_password": "default_token_password",
    "device": "cpu",
    "timeout": 600,
    "cache_seed": None,
    "params": {"max_length": 256},
    "use_retrieve_proxy": True,
}

agent_with_number = ConversableAgent(
    "agent_with_number",
    system_message="You are playing a game of guess-my-number. You have the "
    "number 53 in your mind, and I will try to guess it. "
    "If I guess too high, say 'too high', if I guess too low, say 'too low'. ",
    llm_config={"config_list": [model_config]},
    is_termination_msg=lambda msg: "53"
    in msg["content"],  # terminate if the number is guessed by the other agent
    human_input_mode="NEVER",  # never ask for human input
)

agent_guess_number = ConversableAgent(
    "agent_guess_number",
    system_message="I have a number in my mind, and you will try to guess it. "
    "If I say 'too high', you should guess a lower number. If I say 'too low', "
    "you should guess a higher number. ",
    llm_config={"config_list": [model_config]},
    human_input_mode="NEVER",
)

agent_with_number.register_model_client(model_client_cls=OllamaClient)
agent_guess_number.register_model_client(model_client_cls=OllamaClient)

result = agent_with_number.initiate_chat(
    agent_guess_number,
    message="I have a number between 1 and 100. Guess it!",
)
