"""
Gemini API client and service layer.

Provides a unified, reusable client wrapper for interacting with the Google
Gemini Developer API using the official `google-genai` SDK.
"""

from typing import Optional
from google import genai
from google.genai import types
from google.genai.errors import APIError

from .config import config


class GeminiServiceError(Exception):
    """Custom exception wrapper for Gemini API operations."""
    pass


class GeminiClient:
    """
    Reusable client service for Google Gemini Developer API.
    Designed for use by audio transcription and meeting summarization modules.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self._api_key = api_key
        self._model = model or config.GEMINI_MODEL
        self._client: Optional[genai.Client] = None

    def get_client(self) -> genai.Client:
        """
        Lazily initialize and return the authenticated `genai.Client`.
        Validates API key presence before connecting.
        """
        if self._client is None:
            key = self._api_key or config.validate_api_key()
            try:
                self._client = genai.Client(api_key=key)
            except Exception as e:
                raise GeminiServiceError(f"Failed to initialize Gemini Client: {e}") from e
        return self._client

    @property
    def model_name(self) -> str:
        """Returns the configured Gemini model name."""
        return self._model

    def generate_content(
        self,
        contents: list | str,
        system_instruction: Optional[str] = None,
        response_schema: Optional[type] = None,
        response_mime_type: Optional[str] = None,
    ) -> str:
        """
        Reusable content generation method supporting structured output and system instructions.

        :param contents: Prompt string, list of multimodal parts, or file references.
        :param system_instruction: Optional system instruction prompt.
        :param response_schema: Optional Pydantic model for structured output enforcement.
        :param response_mime_type: Optional MIME type (e.g. 'application/json').
        :return: Generated text response.
        :raises GeminiServiceError: On API failure, empty response, or network error.
        """
        client = self.get_client()

        config_params = {}
        if system_instruction:
            config_params["system_instruction"] = system_instruction
        if response_mime_type:
            config_params["response_mime_type"] = response_mime_type
        if response_schema:
            config_params["response_schema"] = response_schema
            if not response_mime_type:
                config_params["response_mime_type"] = "application/json"

        generate_config = types.GenerateContentConfig(**config_params) if config_params else None

        try:
            response = client.models.generate_content(
                model=self._model,
                contents=contents,
                config=generate_config,
            )
        except APIError as e:
            raise GeminiServiceError(f"Gemini API error ({e.code}): {e.message}") from e
        except Exception as e:
            raise GeminiServiceError(f"Gemini generation request failed: {e}") from e

        if not response or not response.text:
            raise GeminiServiceError("Gemini returned an empty or invalid response.")

        return response.text


# Default singleton instance for standard backend usage
gemini_service = GeminiClient()
