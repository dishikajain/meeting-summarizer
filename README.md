# Meeting Summarizer

An automated meeting processing application that transcribes meeting audio and generates structured, action-oriented summaries using Google Gemini models on the Gemini API Free Tier.

## Project Description

Meeting Summarizer is designed to ingest recorded meeting audio files, generate accurate text transcripts, extract key decisions, and produce actionable task lists with explicit owners and deadlines. It features a lightweight FastAPI backend for processing and local SQLite persistence, alongside a responsive, clean vanilla web interface.

## Tech Stack

- **Backend Framework:** FastAPI (Python)
- **AI / ASR & Summarization:** Google Gemini Developer API (`gemini-2.5-flash` via `google-genai` SDK)
- **Database:** SQLite (Python standard library `sqlite3`)
- **Frontend:** Vanilla HTML5, CSS3, JavaScript (no external frameworks or build tooling)
- **Server:** Uvicorn ASGI

## Architecture Overview

```
meeting_summarizer/
├── backend/
│   ├── main.py              # FastAPI application & route endpoints
│   ├── transcriber.py       # Audio transcription via Gemini API
│   ├── summarizer.py        # Structured summarization via Gemini API
│   ├── database.py          # SQLite database connection & CRUD operations
│   ├── models.py            # Pydantic schemas & response validation
│   └── requirements.txt     # Minimal backend dependencies
├── frontend/
│   ├── index.html           # Single-page user interface
│   ├── style.css            # Custom responsive styles & theme
│   └── app.js               # Client-side API interactions & UI logic
├── .env.example             # Environment configuration template
├── .gitignore               # Strict exclusion rules for repository hygiene
└── README.md                # Project documentation
```

### Processing Pipeline

1. **Upload:** User provides an audio recording (`.wav`, `.mp3`, `.aac`, `.ogg`, `.flac` up to 20 MB).
2. **Transcription:** Audio is sent to the Gemini API using `gemini-2.5-flash` to generate a verbatim transcript.
3. **Summarization:** The transcript is analyzed by `gemini-2.5-flash` with a strict JSON schema (`response_schema`) extracting:
   - Executive meeting summary
   - Concrete decisions made
   - Action items (task, owner, deadline)
4. **Persistence:** The transcript, summary, decisions, and action items are saved locally in SQLite.
5. **Display:** The complete structured results and meeting history are presented in the frontend interface.

## Setup & Running (Placeholder)

Detailed setup and execution instructions will be documented as each module is implemented in subsequent phases.

### Prerequisites (Planned)

- Python 3.10+
- Google Gemini API Key (from Google AI Studio Free Tier)

### Environment Configuration (Planned)

Copy `.env.example` to `.env` and provide your Gemini API Key:

```bash
cp .env.example .env
```
