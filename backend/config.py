import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if present
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")


class Config:
    """Centralized application and Gemini configuration."""

    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    MAX_AUDIO_SIZE_MB: int = int(os.getenv("MAX_AUDIO_SIZE_MB", "20"))

    # Explicitly supported audio formats per approved implementation plan
    SUPPORTED_AUDIO_FORMATS: dict[str, str] = {
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".aac": "audio/aac",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
    }

    @classmethod
    def validate_api_key(cls) -> str:
        """
        Validate and return the Gemini API key.
        Raises ValueError if the API key is not configured.
        """
        key = cls.GEMINI_API_KEY.strip()
        if not key or key == "your_gemini_api_key_here":
            raise ValueError(
                "GEMINI_API_KEY is not set. Please set a valid Gemini API key in your .env file or environment variables."
            )
        return key


config = Config()
