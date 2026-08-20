"""
Meeting summarization module using Google Gemini API structured output.

Handles:
- Processing meeting transcripts with Gemini 2.5 Flash
- Enforcing structured output matching MeetingSummary schema
- Extracting concise summary, decisions, and action items
- Enforcing anti-hallucination rules and fallback "Not specified" for missing owners/deadlines
"""

from typing import Optional
from pydantic import ValidationError

from .models import MeetingSummary, ActionItem
from .gemini_client import GeminiClient, GeminiServiceError, gemini_service

# Approved system prompt enforcing anti-hallucination and extraction rules
SUMMARIZATION_SYSTEM_INSTRUCTION = (
    "You are a professional meeting analyst. "
    "Analyze the following meeting transcript carefully.\n\n"
    "Rules:\n"
    "- ONLY include information that is explicitly stated in the transcript.\n"
    "- NEVER invent, infer, or assume owners, deadlines, or decisions that are not stated.\n"
    "- If an action item's owner is not mentioned, set owner to \"Not specified\".\n"
    "- If a deadline is not mentioned, set deadline to \"Not specified\".\n"
    "- Decisions must be concrete conclusions reached, not open discussion topics."
)


class SummarizationError(Exception):
    """Exception raised when summarization fails due to validation or API errors."""
    pass


def summarize_transcript(
    transcript: str,
    client_service: Optional[GeminiClient] = None,
) -> MeetingSummary:
    """
    Generate a structured meeting summary from a text transcript using Gemini 2.5 Flash.

    :param transcript: The verbatim text transcript of the meeting.
    :param client_service: Optional GeminiClient instance (defaults to global gemini_service).
    :return: Validated MeetingSummary object containing summary, decisions, and action items.
    :raises SummarizationError: If the transcript is empty, API call fails, or output schema fails validation.
    """
    cleaned_transcript = transcript.strip() if transcript else ""
    if not cleaned_transcript:
        raise SummarizationError("Transcript is empty. Cannot generate summary.")

    service = client_service or gemini_service

    user_prompt = f"Transcript:\n{cleaned_transcript}"

    try:
        raw_json = service.generate_content(
            contents=user_prompt,
            system_instruction=SUMMARIZATION_SYSTEM_INSTRUCTION,
            response_schema=MeetingSummary,
            response_mime_type="application/json",
        )
    except GeminiServiceError as e:
        raise SummarizationError(f"Gemini API summarization failed: {e}") from e
    except Exception as e:
        raise SummarizationError(f"Unexpected error during summarization: {e}") from e

    try:
        meeting_summary = MeetingSummary.model_validate_json(raw_json)
    except ValidationError as e:
        raise SummarizationError(f"Failed to validate structured summary output: {e}") from e
    except Exception as e:
        raise SummarizationError(f"Failed to parse summary response JSON: {e}") from e

    # Post-process: ensure missing/blank owner or deadline values default to "Not specified"
    sanitized_actions: list[ActionItem] = []
    for item in meeting_summary.action_items:
        owner = item.owner.strip() if item.owner else ""
        if not owner or owner.lower() in ("null", "none", "n/a", "unknown"):
            owner = "Not specified"

        deadline = item.deadline.strip() if item.deadline else ""
        if not deadline or deadline.lower() in ("null", "none", "n/a", "unknown"):
            deadline = "Not specified"

        sanitized_actions.append(
            ActionItem(
                task=item.task.strip(),
                owner=owner,
                deadline=deadline,
            )
        )

    return MeetingSummary(
        summary=meeting_summary.summary.strip(),
        decisions=[d.strip() for d in meeting_summary.decisions if d.strip()],
        action_items=sanitized_actions,
    )
