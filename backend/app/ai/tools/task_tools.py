"""Task and meeting tools."""
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from uuid import UUID

from dateutil import parser as dateutil_parser

from app.ai import model_router
from app.ai.tools.base import ToolSpec

logger = logging.getLogger("app.ai.tools.task_tools")

_NOTES_LIMIT = 6000
_ACTION_ITEMS_LIMIT = 20

_WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


def _parse_meeting_datetime(value):
    """Coerce an LLM-supplied meeting time into a timezone-aware datetime.

    Accepts ISO 8601 (``2026-08-13T10:00:00Z``), written dates via dateutil
    (``Aug 13, 2026 10:00 AM``) and the natural-language phrases models tend
    to emit for a meeting request (``Monday at 8:00 AM``, ``tomorrow at 3 PM``,
    ``next Friday``). Returns ``None`` when the value cannot be interpreted so
    the meeting is still created (without a scheduled time) instead of failing
    the turn with a ``timestamptz`` parse error.
    """
    if value is None or isinstance(value, datetime):
        return value
    raw = str(value).strip()
    if not raw:
        return None

    def aware(dt: datetime) -> datetime:
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    # 1) ISO 8601 / machine timestamps.
    try:
        return aware(datetime.fromisoformat(raw.replace("Z", "+00:00")))
    except ValueError:
        pass

    now = datetime.now(timezone.utc)

    def clock():
        """Extract (hour, minute) from phrases like '8:00 AM' or '17:30'."""
        m = re.search(
            r"(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)?", raw, re.IGNORECASE
        )
        if not m:
            return None
        hour, minute = int(m.group(1)), int(m.group(2) or 0)
        ampm = (m.group(3) or "").lower().replace(".", "")
        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        if hour > 23 or minute > 59:
            return None
        return hour, minute

    # A written date (year or month name) means dateutil can resolve it exactly;
    # weekday/tomorrow phrases only make sense when no date is present.
    has_full_date = bool(
        re.search(
            r"\b(19|20)\d{2}\b|"
            r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*",
            raw,
            re.IGNORECASE,
        )
    )

    if not has_full_date:
        # 2) "tomorrow at 3 PM" / "today at 5pm" / "tonight at 8".
        day_m = re.search(r"\b(tomorrow|tonight|today)\b", raw, re.IGNORECASE)
        if day_m:
            word = day_m.group(1).lower()
            base = now.date() + timedelta(days=1) if word == "tomorrow" else now.date()
            t = clock()
            hour, minute = t if t else (20 if word == "tonight" else 9)
            return aware(datetime(base.year, base.month, base.day, hour, minute))

        # 3) "Monday at 8:00 AM" / "next Friday 9am" / "this monday".
        wk = re.search(
            r"\b(next|this|coming)?\s*?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            raw,
            re.IGNORECASE,
        )
        if wk:
            prefix = (wk.group(1) or "").lower()
            target = _WEEKDAYS[wk.group(2).lower()]
            days_ahead = (target - now.weekday()) % 7
            if prefix == "next":
                days_ahead = 7 if days_ahead == 0 else days_ahead + 7
            elif prefix == "" and days_ahead == 0:
                # "Monday" said on a Monday means the coming one, not today.
                days_ahead = 7
            date = now.date() + timedelta(days=days_ahead)
            t = clock()
            hour, minute = t if t else (9, 0)
            return aware(datetime(date.year, date.month, date.day, hour, minute))

    # 4) Last resort: written dates, "10:00 AM" alone, etc.
    try:
        return aware(dateutil_parser.parse(raw, fuzzy=True))
    except (ValueError, TypeError, OverflowError):
        return None


def _uuid(value):
    try:
        return UUID(str(value)) if value else None
    except (ValueError, TypeError):
        return None


def _generated_documents_dir():
    from pathlib import Path

    return Path(__file__).resolve().parent.parent.parent / "generated_documents"


def _resolve_audio_bytes(db, org_id, audio_url):
    """Locate an uploaded audio file via storage_files and read its bytes.

    ``audio_url`` may be the storage row's ``file_path``, ``url`` or
    ``file_name``. Bytes come from the same local generated-documents
    convention used by the PDF/storage flow — no new upload mechanism.
    Returns ``(bytes, filename)`` or ``None``.
    """
    from pathlib import Path
    from urllib.parse import unquote

    from app.models.storage import StorageFile

    if not audio_url:
        return None
    url = str(audio_url).strip()
    if not url:
        return None

    query = db.query(StorageFile).filter(StorageFile.organization_id == org_id)
    row = (
        query.filter(StorageFile.file_path == url).first()
        or query.filter(StorageFile.url == url).first()
        or query.filter(StorageFile.file_name == url).first()
    )
    if row is None:
        return None

    local = None
    file_path = (row.file_path or "").strip()
    if file_path:
        p = Path(file_path)
        if p.is_absolute():
            local = p
        elif file_path.startswith("/documents/"):
            candidate = _generated_documents_dir() / unquote(file_path[len("/documents/") :])
            local = candidate if candidate.is_file() else None
    if local is None and row.url:
        p = Path(row.url)
        if p.is_absolute() and p.is_file():
            local = p
    try:
        if local is None or not local.is_file():
            return None
        return local.read_bytes(), row.file_name or local.name
    except OSError:
        return None


def list_tasks(db, org_id, user_id, arguments: dict):
    from app.models.task import Task

    query = db.query(Task).filter(Task.organization_id == org_id)
    if arguments.get("status") and arguments["status"].lower() != "all":
        query = query.filter(Task.status == arguments["status"])
    if arguments.get("assigned_to"):
        query = query.filter(Task.assigned_to == _uuid(arguments["assigned_to"]))
    rows = query.order_by(Task.created_at.desc()).limit(arguments.get("limit", 50)).all()
    return [
        {
            "id": str(t.id),
            "title": t.title,
            "description": t.description,
            "priority": t.priority,
            "status": t.status,
            "ai_created": bool(t.ai_created),
            "due_date": str(t.due_date) if t.due_date else None,
        }
        for t in rows
    ]


def create_task(db, org_id, user_id, arguments: dict):
    from app.models.task import Task

    task = Task(
        organization_id=org_id,
        assigned_to=_uuid(arguments.get("assigned_to")),
        created_by=_uuid(user_id),
        title=arguments["title"],
        description=arguments.get("description"),
        priority=arguments.get("priority", "medium"),
        status=arguments.get("status", "todo"),
        ai_created=True,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return {"id": str(task.id), "title": task.title, "status": task.status, "ai_created": True}


def list_meetings(db, org_id, user_id, arguments: dict):
    from app.models.meeting import Meeting

    rows = (
        db.query(Meeting)
        .filter(Meeting.organization_id == org_id)
        .order_by(Meeting.start_time.desc())
        .limit(arguments.get("limit", 50))
        .all()
    )
    return [
        {
            "id": str(m.id),
            "title": m.title,
            "start_time": str(m.start_time) if m.start_time else None,
            "summary": m.summary,
        }
        for m in rows
    ]


def _attendee_emails(participants) -> list[str]:
    """Extract plain email strings from a participants JSONB value."""
    if not isinstance(participants, list):
        return []
    emails = []
    for item in participants:
        if isinstance(item, str) and item:
            emails.append(item)
        elif isinstance(item, dict) and item.get("email"):
            emails.append(item["email"])
    return emails


def create_meeting(db, org_id, user_id, arguments: dict):
    from app.models.meeting import Meeting

    start_time = _parse_meeting_datetime(arguments.get("start_time"))
    end_time = _parse_meeting_datetime(arguments.get("end_time"))

    now = datetime.now(timezone.utc)
    if start_time is not None and start_time < now - timedelta(minutes=1):
        # The model sometimes resolves "Monday at 8 AM" to a date that has
        # already passed. Reject it so the model retries with a future time
        # instead of silently scheduling a meeting in the past.
        return {
            "error": (
                "The meeting start time is in the past "
                f"({start_time.isoformat()}; now is {now.isoformat()}). "
                "Schedule the meeting for a future time, e.g. the next "
                "occurrence of that weekday."
            )
        }

    if start_time is not None and end_time is None:
        # The model often supplies only a start time; default to a 1-hour slot
        # so the meeting can still sync to Google Calendar.
        end_time = start_time + timedelta(hours=1)

    meeting = Meeting(
        organization_id=org_id,
        title=arguments["title"],
        start_time=start_time,
        end_time=end_time,
        participants=arguments.get("participants", []),
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    result = {
        "id": str(meeting.id),
        "title": meeting.title,
        "created": True,
        "calendar_synced": False,
    }

    # Calendar sync is best-effort: internal scheduling must never fail
    # because Google Calendar is disconnected or hiccups.
    if meeting.start_time is None or meeting.end_time is None:
        return result

    try:
        from app.integrations.google_calendar.service import get_client

        created = get_client(db, org_id).create_event(
            title=meeting.title or "",
            start_time=meeting.start_time,
            end_time=meeting.end_time,
            attendees=_attendee_emails(meeting.participants),
        )
        meeting.external_event_id = created.get("event_id")
        db.add(meeting)
        db.commit()
        result["calendar_synced"] = True
        result["external_event_id"] = created.get("event_id")
        result["html_link"] = created.get("html_link")
    except Exception as exc:  # noqa: BLE001 - never let Calendar break scheduling
        db.rollback()  # keep the session usable for the rest of the turn
        logger.warning(
            "google calendar sync skipped for meeting %s: %s (%s)",
            meeting.id,
            exc.__class__.__name__,
            exc,
        )
    return result


def _summary_notes_prompt(notes: str) -> list[dict]:
    return [
        {
            "role": "system",
            "content": (
                "You summarize meeting notes. Respond with ONLY a JSON object "
                "using exactly these keys: summary (2-4 sentences), "
                "action_items (a list of {\"item\": str, \"owner\": str or null, "
                "\"due_hint\": str or null}), key_decisions (a list of strings). "
                "Do not invent facts that are not in the notes."
            ),
        },
        {
            "role": "user",
            "content": notes,
        },
    ]


def _parse_meeting_json(raw) -> dict | None:
    if not raw or not isinstance(raw, str):
        return None
    text = raw.strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
    except (json.JSONDecodeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _coerce_action_items(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    items = []
    for entry in value[: _ACTION_ITEMS_LIMIT]:
        if not isinstance(entry, dict):
            continue
        def text(v, limit=200):
            return str(v)[:limit] if v is not None else None
        item = text(entry.get("item")) or ""
        if not item:
            continue
        items.append(
            {
                "item": item,
                "owner": text(entry.get("owner")),
                "due_hint": text(entry.get("due_hint")),
            }
        )
    return items


def _coerce_key_decisions(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(d)[:300] for d in value if isinstance(d, str)][:10]


def _fallback_summary(notes: str, removed_chars: int) -> str:
    lines = [ln.strip() for ln in notes.strip().splitlines() if ln.strip()]
    if not lines:
        return "No meeting summary could be generated."
    lead = lines[0]
    summary = f"{lead}." if not lead.endswith(".") else lead
    if removed_chars:
        summary += f" (notes were truncated by {removed_chars} chars)"
    return summary[:600]


def _clean_text(value) -> str:
    return str(value).strip() if value else ""


def summarize_meeting(db, org_id, user_id, arguments: dict):
    from app.models.meeting import Meeting

    meeting = (
        db.query(Meeting)
        .filter(
            Meeting.id == _uuid(arguments.get("meeting_id")),
            Meeting.organization_id == org_id,
        )
        .first()
    )
    if meeting is None:
        return {"error": "Meeting not found"}

    notes = str(arguments.get("notes") or "").strip()
    if not notes:
        return {"error": "notes is required"}

    # NOTE: Meeting.transcript is intentionally reused to hold typed/pasted
    # notes dated via summarize_meeting AND audio-derived transcripts appended
    # by transcribe_meeting_audio. One column, two writers — the single place
    # for the meeting's recorded content.
    meeting.transcript = notes

    messages_notes = notes
    removed_chars = 0
    if len(notes) > _NOTES_LIMIT:
        removed_chars = len(notes) - _NOTES_LIMIT
        messages_notes = notes[: _NOTES_LIMIT]

    summary = None
    action_items: list[dict] = []
    key_decisions: list[str] = []
    source = "data"
    try:
        raw = model_router.complete(_summary_notes_prompt(messages_notes), temperature=0.2)
        parsed = _parse_meeting_json(raw)
        if parsed is not None:
            parsed_summary = _clean_text(parsed.get("summary"))
            if parsed_summary:
                summary = parsed_summary
                action_items = _coerce_action_items(parsed.get("action_items"))
                key_decisions = _coerce_key_decisions(parsed.get("key_decisions"))
                source = "llm"
    except Exception:  # noqa: BLE001 - rate limit / no key / parse issues -> fallback
        summary = None

    if summary is None:
        summary = _fallback_summary(notes, removed_chars)
        action_items = []
        key_decisions = []

    meeting.summary = summary
    meeting.action_items = action_items
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    return {
        "meeting_id": str(meeting.id),
        "summary": summary,
        "action_items": action_items,
        "key_decisions": key_decisions,
        "source": source,
        "truncated": bool(removed_chars),
    }


def transcribe_meeting_audio(db, org_id, user_id, arguments: dict):
    """Transcribe an uploaded meeting audio file and persist the transcript.

    Uses a hosted STT API (app.integrations.transcription). Deliberately does
    NOT auto-chain into summarize_meeting — the agent/user can call that next
    with the returned transcript. Structured errors everywhere; never raises.
    """
    from app.models.meeting import Meeting

    meeting = (
        db.query(Meeting)
        .filter(
            Meeting.id == _uuid(arguments.get("meeting_id")),
            Meeting.organization_id == org_id,
        )
        .first()
    )
    if meeting is None:
        return {"error": "Meeting not found"}

    audio = _resolve_audio_bytes(db, org_id, arguments.get("audio_url"))
    if audio is None:
        return {"error": "Audio file not found for audio_url"}

    from app.integrations.transcription.client import (
        TranscriptionError,
        TranscriptionNotConfiguredError,
        transcribe_audio,
    )

    audio_bytes, filename = audio
    try:
        result = transcribe_audio(audio_bytes, filename)
    except TranscriptionNotConfiguredError:
        return {"error": "Transcription not configured: set OPENAI_API_KEY"}
    except TranscriptionError as exc:
        return {"error": f"Transcription failed: {exc}"}
    except Exception as exc:  # noqa: BLE001 - never crash the agent loop
        return {"error": f"Transcription failed: {exc}"}

    text = str(result.get("text") or "").strip()
    existing = (meeting.transcript or "").strip()
    meeting.transcript = existing + "\n\n" + text if existing else text
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    return {
        "meeting_id": str(meeting.id),
        "transcript": meeting.transcript,
        "duration_seconds": result.get("duration_seconds"),
        "source": "audio",
    }


TASK_TOOLS: dict[str, ToolSpec] = {
    "list_tasks": ToolSpec(
        name="list_tasks",
        description="List tasks, optionally filtered by status or assignee.",
        parameters={
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "assigned_to": {"type": "string"},
                "limit": {"type": "integer"},
            },
        },
        handler=list_tasks,
    ),
    "create_task": ToolSpec(
        name="create_task",
        description="Create a task (marked as AI-created).",
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
                "status": {"type": "string"},
                "assigned_to": {"type": "string"},
            },
            "required": ["title"],
        },
        handler=create_task,
    ),
    "list_meetings": ToolSpec(
        name="list_meetings",
        description="List the organization's meetings.",
        parameters={
            "type": "object",
            "properties": {"limit": {"type": "integer"}},
        },
        handler=list_meetings,
    ),
    "create_meeting": ToolSpec(
        name="create_meeting",
        description="Schedule a meeting.",
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "start_time": {
                    "type": "string",
                    "description": (
                        "ISO 8601 datetime in the FUTURE, e.g. 2026-08-13T10:00:00Z. "
                        "Natural language like 'Monday at 8:00 AM' (meaning the next "
                        "upcoming Monday) is also accepted. Never use a date in the past."
                    ),
                },
                "end_time": {
                    "type": "string",
                    "description": (
                        "ISO 8601 datetime, e.g. 2026-08-13T11:00:00Z. "
                        "Natural language like 'tomorrow at 5 PM' is also accepted."
                    ),
                },
                "participants": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title"],
        },
        handler=create_meeting,
    ),
    "summarize_meeting": ToolSpec(
        name="summarize_meeting",
        description=(
            "Summarize a meeting's typed notes into a concise summary, action "
            "items and key decisions, persisting them on the meeting."
        ),
        parameters={
            "type": "object",
            "properties": {
                "meeting_id": {"type": "string", "format": "uuid"},
                "notes": {"type": "string", "description": "Raw meeting notes text."},
            },
            "required": ["meeting_id", "notes"],
        },
        handler=summarize_meeting,
    ),
    "transcribe_meeting_audio": ToolSpec(
        name="transcribe_meeting_audio",
        description=(
            "Transcribe an uploaded meeting audio file via a hosted speech-to-text "
            "API and append the transcript to the meeting's stored content. "
            "Does NOT summarize — call summarize_meeting separately on the "
            "returned transcript if a summary is wanted."
        ),
        parameters={
            "type": "object",
            "properties": {
                "meeting_id": {"type": "string", "format": "uuid"},
                "audio_url": {
                    "type": "string",
                    "description": (
                        "URL/path of an already-uploaded audio file "
                        "(a storage_files file_path, url or file_name)."
                    ),
                },
            },
            "required": ["meeting_id", "audio_url"],
        },
        handler=transcribe_meeting_audio,
    ),
}