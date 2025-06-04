"""
This module provides the DeepSeek language model implementation.
"""

import json
import logging
from typing import List, Dict, Any, Optional

from openai import OpenAI
from .abstract_language_model import AbstractLanguageModel

class DeepSeek(AbstractLanguageModel):
    """
    DeepSeek provides access to the DeepSeek-V3 language model through their API.
    """

    def __init__(
        self,
        config_path: str,
        model_name: str = "deepseek-chat",
        cache: bool = True,
    ) -> None:
        """
        Initialize the DeepSeek language model.

        :param config_path: Path to the configuration file.
        :type config_path: str
        :param model_name: Name of the model to use.
        :type model_name: str
        :param cache: Whether to cache the responses.
        :type cache: bool
        """
        super().__init__(config_path, model_name, cache)
        self.base_url = self.config["deepseek"]["base_url"]
        self.api_key = self.config["deepseek"]["api_key"]
        self.model = self.config["deepseek"]["model_id"]
        self.prompt_token_cost = self.config["deepseek"]["prompt_token_cost"]
        self.response_token_cost = self.config["deepseek"]["response_token_cost"]
        self.temperature = self.config["deepseek"]["temperature"]
        self.max_tokens = self.config["deepseek"]["max_tokens"]
        
        # Initialize OpenAI client
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

    def get_response_texts(self, response: Any) -> List[str]:
        """
        Extract the response texts from the API response.

        :param response: Response from the API.
        :type response: Any
        :return: List of response texts.
        :rtype: List[str]
        """
        try:
            # 添加调试日志
            logging.debug(f"Response type: {type(response)}")
            logging.debug(f"Response content: {response}")
            
            # 如果response是字典类型（旧版SDK或直接API响应）
            if isinstance(response, dict):
                return [choice["message"]["content"].strip() for choice in response["choices"]]
            # 如果response是列表类型（可能是Deepseek特殊格式）
            elif isinstance(response, list):
                return [item["message"]["content"].strip() for item in response]
            # 如果response是OpenAI新版SDK的响应对象
            else:
                return [choice.message.content.strip() for choice in response.choices]
                
        except Exception as e:
            logging.error(f"Error extracting response texts: {str(e)}")
            return ["Error: " + str(e)]

    def query(
        self,
        prompt: str,
        num_responses: int = 1,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stop: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Query the DeepSeek language model.

        :param prompt: The prompt to query the model with.
        :type prompt: str
        :param num_responses: Number of responses to generate.
        :type num_responses: int
        :param max_tokens: Maximum number of tokens to generate.
        :type max_tokens: Optional[int]
        :param temperature: Temperature to use for generation.
        :type temperature: Optional[float]
        :param stop: Stop sequences to use.
        :type stop: Optional[List[str]]
        :return: List of responses from the model.
        :rtype: List[str]
        """
        # Prepare the messages
        messages = [{"role": "user", "content": prompt}]

        try:
            # Make the API call using the new format
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                n=num_responses,
                temperature=temperature if temperature is not None else self.temperature,
                max_tokens=max_tokens if max_tokens is not None else self.max_tokens,
                stop=stop,
            )
            
            # 添加调试日志
            logging.debug(f"Raw API response type: {type(response)}")
            logging.debug(f"Raw API response: {response}")
            
            # Update costs using object attribute access
            self.cost += (
                response.usage.prompt_tokens * self.prompt_token_cost
                + response.usage.completion_tokens * self.response_token_cost
            ) / 1000.0

            # Extract response texts using the abstract method
            return self.get_response_texts(response)

        except Exception as e:
            logging.error(f"Error querying DeepSeek API: {str(e)}")
            return ["Error: " + str(e)]

    def batch_query(
        self,
        prompts: List[str],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stop: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Query the DeepSeek language model with multiple prompts.

        :param prompts: The prompts to query the model with.
        :type prompts: List[str]
        :param max_tokens: Maximum number of tokens to generate.
        :type max_tokens: Optional[int]
        :param temperature: Temperature to use for generation.
        :type temperature: Optional[float]
        :param stop: Stop sequences to use.
        :type stop: Optional[List[str]]
        :return: List of responses from the model.
        :rtype: List[str]
        """
        results = []
        for prompt in prompts:
            results.extend(
                self.query(
                    prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stop=stop,
                )
            )
        return results 