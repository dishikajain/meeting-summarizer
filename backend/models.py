"""
Data models and Pydantic schemas for Meeting Summarizer.

Defines schemas for:
- Structured LLM output (MeetingSummary, ActionItem)
- API requests (SummarizeRequest)
- API responses (MeetingDetailResponse, MeetingListItemResponse, TranscriptionResponse, HealthResponse)
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Structured LLM Output Schemas
# ---------------------------------------------------------------------------

class ActionItem(BaseModel):
    """Represents an extracted task with its assigned owner and deadline."""
    task: str = Field(
        description="The specific action or task to be completed"
    )
    owner: Optional[str] = Field(
        default="Not specified",
        description="Person or entity responsible. Must be 'Not specified' if not explicitly stated in the transcript."
    )
    deadline: Optional[str] = Field(
        default="Not specified",
        description="Target completion date or timeframe. Must be 'Not specified' if not explicitly stated in the transcript."
    )

    @field_validator("owner", "deadline", mode="before")
    @classmethod
    def set_default_if_none_or_blank(cls, v: Optional[str]) -> str:
        if v is None:
            return "Not specified"
        s = str(v).strip()
        if not s or s.lower() in ("null", "none", "n/a", "unknown"):
            return "Not specified"
        return s


class MeetingSummary(BaseModel):
    """
    Schema enforced for structured meeting summary generation by Gemini
    using response_schema.
    """
    summary: str = Field(
        description="Concise 3-5 sentence executive summary of the meeting."
    )
    decisions: list[str] = Field(
        default_factory=list,
        description="List of concrete decisions reached during the meeting."
    )
    action_items: list[ActionItem] = Field(
        default_factory=list,
        description="List of action items extracted from the meeting."
    )


# ---------------------------------------------------------------------------
# API Request & Response Schemas
# ---------------------------------------------------------------------------

class SummarizeRequest(BaseModel):
    """Request payload schema for POST /summarize endpoint."""
    transcript: str = Field(
        ...,
        description="The verbatim meeting transcript to summarize.",
        min_length=1,
    )


class TranscriptionResponse(BaseModel):
    """Response schema for POST /transcribe endpoint."""
    transcript: str = Field(
        description="The verbatim text transcript generated from audio."
    )


class MeetingDetailResponse(BaseModel):
    """Full meeting record schema returned by POST /process and GET /meetings/{id}."""
    id: int
    filename: str
    created_at: str
    transcript: str
    summary: str
    decisions: list[str]
    action_items: list[ActionItem]


class MeetingListItemResponse(BaseModel):
    """Summary item schema for GET /meetings listing in reverse-chronological order."""
    id: int
    filename: str
    created_at: str
    summary: str


class HealthResponse(BaseModel):
    """Response schema for GET /health endpoint."""
    status: str
    model: str
