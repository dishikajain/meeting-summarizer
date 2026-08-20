"""
FastAPI application entry point and route definitions.

Provides endpoints for:
- GET /health           - Health check and configured model verification
- POST /transcribe      - Audio transcription via Gemini Files API
- POST /summarize       - Structured meeting summary extraction from transcript
- POST /process         - End-to-end audio processing (transcribe + summarize + persist)
- GET /meetings         - List all stored meetings (newest first)
- GET /meetings/{id}    - Retrieve a single meeting by ID
"""

from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from .config import config
from .database import init_db, insert_meeting, get_meeting_by_id, get_all_meetings
from .gemini_client import gemini_service, GeminiServiceError
from .transcriber import transcribe_audio, AudioValidationError
from .summarizer import summarize_transcript, SummarizationError
from .models import (
    HealthResponse,
    TranscriptionResponse,
    SummarizeRequest,
    MeetingSummary,
    MeetingDetailResponse,
    MeetingListItemResponse,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle event handler: ensures SQLite database tables are initialized on startup."""
    init_db()
    yield


app = FastAPI(
    title="Meeting Summarizer API",
    description="Automated meeting audio transcription and structured summarization powered by Google Gemini 2.5 Flash on the Gemini API Free Tier.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for local web interface access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check endpoint",
    tags=["System"],
)
async def health_check() -> HealthResponse:
    """
    Return service health status and configured Gemini model name.
    Does not make an external API call.
    """
    return HealthResponse(
        status="ok",
        model=config.GEMINI_MODEL,
    )


@app.post(
    "/transcribe",
    response_model=TranscriptionResponse,
    summary="Transcribe audio file",
    tags=["Audio & Transcription"],
)
async def transcribe_endpoint(
    audio: UploadFile = File(..., description="Meeting audio file (.wav, .mp3, .aac, .ogg, .flac)")
) -> TranscriptionResponse:
    """
    Accept an uploaded audio file, validate format/size, and transcribe using Gemini 2.5 Flash.
    """
    if not audio.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename missing from upload.",
        )

    try:
        file_bytes = await audio.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded audio file: {e}",
        )

    try:
        transcript_text = transcribe_audio(
            file_input=file_bytes,
            filename=audio.filename,
        )
    except AudioValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except (GeminiServiceError, Exception) as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transcription failed: {e}",
        )

    return TranscriptionResponse(transcript=transcript_text)


@app.post(
    "/summarize",
    response_model=MeetingSummary,
    summary="Generate structured summary from transcript text",
    tags=["Summarization"],
)
async def summarize_endpoint(
    request: SummarizeRequest
) -> MeetingSummary:
    """
    Accept verbatim transcript text and generate a structured summary, decisions, and action items.
    """
    transcript_text = request.transcript.strip()
    if not transcript_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transcript text cannot be empty.",
        )

    try:
        summary_result = summarize_transcript(transcript=transcript_text)
    except SummarizationError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Summarization failed: {e}",
        )

    return summary_result


@app.post(
    "/process",
    response_model=MeetingDetailResponse,
    summary="Full pipeline: upload audio -> transcribe -> summarize -> persist",
    tags=["Pipeline"],
)
async def process_endpoint(
    audio: UploadFile = File(..., description="Meeting audio file (.wav, .mp3, .aac, .ogg, .flac)")
) -> MeetingDetailResponse:
    """
    Execute full meeting processing pipeline:
    1. Read and validate uploaded audio.
    2. Transcribe via Gemini Files API.
    3. Generate structured summary, decisions, and action items via Gemini.
    4. Persist all results to SQLite database.
    5. Return stored meeting record.
    """
    if not audio.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename missing from upload.",
        )

    try:
        file_bytes = await audio.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded audio file: {e}",
        )

    # 1. Transcribe
    try:
        transcript_text = transcribe_audio(
            file_input=file_bytes,
            filename=audio.filename,
        )
    except AudioValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except (GeminiServiceError, Exception) as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transcription failed during processing: {e}",
        )

    # 2. Summarize
    try:
        summary_result = summarize_transcript(transcript=transcript_text)
    except SummarizationError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Summarization failed during processing: {e}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Summarization failed during processing: {e}",
        )

    # 3. Persist to SQLite
    try:
        saved_meeting = insert_meeting(
            filename=audio.filename,
            transcript=transcript_text,
            summary=summary_result.summary,
            decisions=summary_result.decisions,
            action_items=summary_result.action_items,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database persistence failed: {e}",
        )

    return saved_meeting


@app.get(
    "/meetings",
    response_model=list[MeetingListItemResponse],
    summary="List all stored meetings in reverse-chronological order",
    tags=["Meetings"],
)
async def list_meetings_endpoint() -> list[MeetingListItemResponse]:
    """
    Retrieve all meetings stored in SQLite, ordered newest first.
    """
    try:
        meetings = get_all_meetings()
        return meetings
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve meetings from database: {e}",
        )


@app.get(
    "/meetings/{meeting_id}",
    response_model=MeetingDetailResponse,
    summary="Retrieve single meeting details by ID",
    tags=["Meetings"],
)
async def get_meeting_endpoint(meeting_id: int) -> MeetingDetailResponse:
    """
    Retrieve full transcript, summary, decisions, and action items for a given meeting ID.
    Returns 404 if the record is not found.
    """
    try:
        meeting = get_meeting_by_id(meeting_id=meeting_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database query failed: {e}",
        )

    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meeting with ID {meeting_id} not found.",
        )

    return meeting
