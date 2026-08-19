"""
Audio transcription module using Google Gemini API and Gemini Files API.

Handles:
- Validation of audio formats (.wav, .mp3, .aac, .ogg, .flac) and size (<= 20 MB)
- Uploading audio to the Gemini Files API
- Invoking Gemini 2.5 Flash with the approved verbatim transcription prompt
- Automatic cleanup of the uploaded Files API reference
"""

import io
import os
from pathlib import Path
from typing import Optional, Union

from google.genai import types
from google.genai.errors import APIError

from .config import config
from .gemini_client import GeminiClient, GeminiServiceError, gemini_service

# Approved system prompt for verbatim audio transcription
TRANSCRIPTION_PROMPT = (
    "You are an expert meeting transcriptionist. "
    "Transcribe the following meeting audio exactly as spoken. "
    "Preserve all speaker content. Do not summarize or omit any spoken content. "
    "Output only the verbatim transcript text, with no additional commentary."
)


class AudioValidationError(Exception):
    """Exception raised when an audio file fails format or size validation."""
    pass


def validate_audio_file(
    filename: str,
    file_bytes: bytes,
    max_size_mb: Optional[int] = None,
) -> str:
    """
    Validate that the uploaded audio file has an allowed extension and is within size limits.

    :param filename: Name of the uploaded file (e.g. 'meeting.mp3').
    :param file_bytes: Raw bytes of the audio content.
    :param max_size_mb: Optional override for max size in megabytes (default: from config).
    :return: The validated MIME type string.
    :raises AudioValidationError: If extension is unsupported or file size exceeds limit.
    """
    limit_mb = max_size_mb or config.MAX_AUDIO_SIZE_MB
    max_bytes = limit_mb * 1024 * 1024

    if len(file_bytes) == 0:
        raise AudioValidationError("Audio file is empty.")

    if len(file_bytes) > max_bytes:
        raise AudioValidationError(
            f"File size ({len(file_bytes) / (1024 * 1024):.2f} MB) exceeds the maximum allowed limit of {limit_mb} MB."
        )

    ext = Path(filename).suffix.lower()
    if ext not in config.SUPPORTED_AUDIO_FORMATS:
        allowed = ", ".join(config.SUPPORTED_AUDIO_FORMATS.keys())
        raise AudioValidationError(
            f"Unsupported audio format '{ext}'. Allowed formats: {allowed}."
        )

    return config.SUPPORTED_AUDIO_FORMATS[ext]


def transcribe_audio(
    file_input: Union[bytes, io.IOBase, str, Path],
    filename: str,
    mime_type: Optional[str] = None,
    client_service: Optional[GeminiClient] = None,
) -> str:
    """
    Transcribe meeting audio using Gemini 2.5 Flash via the Gemini Files API.

    1. Validates audio format and size (if bytes provided).
    2. Uploads audio stream to Gemini Files API.
    3. Calls Gemini model with verbatim transcription prompt.
    4. Explicitly deletes uploaded file reference after transcription.
    5. Returns the verbatim transcript string.

    :param file_input: Raw audio bytes, file-like object, or file path.
    :param filename: Original filename for extension and validation.
    :param mime_type: Optional MIME type (inferred from filename if not given).
    :param client_service: Optional GeminiClient instance (defaults to global service).
    :return: Extracted verbatim transcript text.
    :raises AudioValidationError: If validation fails.
    :raises GeminiServiceError: If Gemini API upload or transcription fails.
    """
    service = client_service or gemini_service
    client = service.get_client()

    # Determine bytes and validate
    if isinstance(file_input, (bytes, bytearray)):
        detected_mime = validate_audio_file(filename, bytes(file_input))
        resolved_mime = mime_type or detected_mime
        audio_stream = io.BytesIO(file_input)
    elif isinstance(file_input, io.IOBase):
        ext = Path(filename).suffix.lower()
        if ext not in config.SUPPORTED_AUDIO_FORMATS:
            allowed = ", ".join(config.SUPPORTED_AUDIO_FORMATS.keys())
            raise AudioValidationError(
                f"Unsupported audio format '{ext}'. Allowed formats: {allowed}."
            )
        resolved_mime = mime_type or config.SUPPORTED_AUDIO_FORMATS[ext]
        audio_stream = file_input
    elif isinstance(file_input, (str, Path)):
        path = Path(file_input)
        if not path.exists():
            raise AudioValidationError(f"Audio file not found: {path}")
        file_bytes = path.read_bytes()
        detected_mime = validate_audio_file(filename or path.name, file_bytes)
        resolved_mime = mime_type or detected_mime
        audio_stream = io.BytesIO(file_bytes)
    else:
        raise AudioValidationError("Invalid audio input type.")

    uploaded_file = None
    try:
        # Step 1: Upload audio file to Gemini Files API
        upload_config = types.UploadFileConfig(mime_type=resolved_mime)
        uploaded_file = client.files.upload(
            file=audio_stream,
            config=upload_config,
        )

        # Step 2: Generate verbatim transcript with gemini-2.5-flash
        response = client.models.generate_content(
            model=service.model_name,
            contents=[TRANSCRIPTION_PROMPT, uploaded_file],
        )

        if not response or not response.text:
            raise GeminiServiceError("Gemini returned an empty transcription response.")

        return response.text.strip()

    except APIError as e:
        raise GeminiServiceError(f"Gemini API error during transcription ({e.code}): {e.message}") from e
    except GeminiServiceError:
        raise
    except Exception as e:
        raise GeminiServiceError(f"Transcription failed: {e}") from e
    finally:
        # Step 3: Clean up Files API reference
        if uploaded_file and hasattr(uploaded_file, "name"):
            try:
                client.files.delete(name=uploaded_file.name)
            except Exception:
                # Suppress non-critical cleanup errors (file auto-expires after 48h anyway)
                pass
