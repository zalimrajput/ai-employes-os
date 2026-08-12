"""Voice chat endpoint tests.

The hosted transcription client is always mocked (no real API is ever hit)
so the wiring/fallback behavior is deterministic. The voice route is
exercised by calling the handler directly with a real DB session.
"""
import io
import sys
import uuid

sys.path.insert(0, ".")

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from starlette.datastructures import Headers, UploadFile

from app.api.v1.ai_chat.routes import MessageCreate, router, send_message, send_voice_message


def _org(db):
    from app.models.organization import Organization

    org = Organization(
        name="Voice Org",
        slug=f"voice-{uuid.uuid4().hex[:10]}",
        settings={},
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _teardown(db, org):
    deletes = [
        "DELETE FROM ai_messages WHERE organization_id = :id",
        "DELETE FROM ai_conversations WHERE organization_id = :id",
        "DELETE FROM users WHERE organization_id = :id",
        "DELETE FROM organizations WHERE id = :id",
    ]
    for statement in deletes:
        db.execute(text(statement), {"id": org.id})
    db.commit()


def _user(db, org):
    from app.models.user import User

    user = User(organization_id=org.id, full_name="Voice Tester")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _conversation(db, org, user):
    from app.models.ai_conversation import AIConversation

    conv = AIConversation(
        organization_id=org.id,
        user_id=user.id,
        title="Voice test",
        status="active",
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def _audio(filename="msg.webm", content=b"\x00audio"):
    return UploadFile(
        file=io.BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": "audio/webm"}),
    )


def _set_transcribe(db_spec, result, exc=None):
    def fake(audio_bytes, filename, mime_type=None):
        if exc is not None:
            raise exc
        return result

    db_spec.setattr(
        "app.integrations.transcription.client.transcribe_audio", fake
    )


@pytest.mark.db
def test_voice_success_feeds_transcribed_text_into_same_turn(db, monkeypatch):
    captured = {}

    def fake_execute_turn(
        db_,
        organization_id,
        user_id,
        conversation,
        user_message,
        employee=None,
        history_messages=None,
        model=None,
        temperature=0.3,
        images=None,
    ):
        captured["text"] = user_message
        captured["conversation"] = conversation
        return "Here is the roadmap summary.", "sales"

    monkeypatch.setattr("app.api.v1.ai_chat.routes.execute_turn", fake_execute_turn)
    _set_transcribe(
        monkeypatch,
        {"text": "Please summarize the roadmap", "duration_seconds": 2.5},
    )

    org = _org(db)
    user = _user(db, org)
    conv = _conversation(db, org, user)

    try:
        result = send_voice_message(
            conversation_id=conv.id,
            audio=_audio(),
            db=db,
            current_user={"sub": str(user.id)},
        )
        assert result["message"] == "Here is the roadmap summary."
        assert result["transcribed_text"] == "Please summarize the roadmap"
        assert result["role"] == "assistant"

        # the exact transcribed text reached the SAME orchestrator entry point
        assert captured["text"] == "Please summarize the roadmap"
        assert captured["conversation"] is conv

        # persisted: user message tagged as voice-originated
        from app.models.ai_message import AIMessage

        db.expire_all()
        messages = (
            db.query(AIMessage)
            .filter(AIMessage.conversation_id == conv.id)
            .order_by(AIMessage.created_at)
            .all()
        )
        assert len(messages) == 2
        user_msg, reply_msg = messages[0], messages[1]
        assert user_msg.role == "user"
        assert user_msg.message == "Please summarize the roadmap"
        assert user_msg.message_metadata == {"source": "voice"}
        assert reply_msg.role == "assistant"
        assert reply_msg.message == result["message"]
    finally:
        _teardown(db, org)


@pytest.mark.db
def test_voice_not_configured_returns_422(db, monkeypatch):
    from app.integrations.transcription.client import TranscriptionNotConfiguredError

    _set_transcribe(monkeypatch, None, exc=TranscriptionNotConfiguredError())

    def unexpected(*args, **kwargs):
        raise AssertionError("no turn when transcription is unconfigured")

    monkeypatch.setattr("app.api.v1.ai_chat.routes.execute_turn", unexpected)

    org = _org(db)
    user = _user(db, org)
    conv = _conversation(db, org, user)

    try:
        with pytest.raises(HTTPException) as excinfo:
            send_voice_message(
                conversation_id=conv.id,
                audio=_audio(),
                db=db,
                current_user={"sub": str(user.id)},
            )
        assert excinfo.value.status_code == 422
        assert "isn't configured" in excinfo.value.detail
    finally:
        _teardown(db, org)


@pytest.mark.db
def test_voice_transcription_failure_returns_422(db, monkeypatch):
    from app.integrations.transcription.client import TranscriptionError

    _set_transcribe(monkeypatch, None, exc=TranscriptionError("upstream 500"))

    def unexpected_turn(*args, **kwargs):
        raise AssertionError("no turn on transcription API failure")

    monkeypatch.setattr("app.api.v1.ai_chat.routes.execute_turn", unexpected_turn)

    org = _org(db)
    user = _user(db, org)
    conv = _conversation(db, org, user)

    try:
        with pytest.raises(HTTPException) as excinfo:
            send_voice_message(
                conversation_id=conv.id,
                audio=_audio(),
                db=db,
                current_user={"sub": str(user.id)},
            )
        assert excinfo.value.status_code == 422
        assert "Voice transcription failed" in excinfo.value.detail
    finally:
        _teardown(db, org)


@pytest.mark.db
def test_voice_empty_transcript_returns_422(db, monkeypatch):
    _set_transcribe(monkeypatch, {"text": "   ", "duration_seconds": 0.4})

    org = _org(db)
    user = _user(db, org)
    conv = _conversation(db, org, user)

    try:
        with pytest.raises(HTTPException) as excinfo:
            send_voice_message(
                conversation_id=conv.id,
                audio=_audio(),
                db=db,
                current_user={"sub": str(user.id)},
            )
        assert excinfo.value.status_code == 422
        assert "No speech recognized" in excinfo.value.detail
    finally:
        _teardown(db, org)


@pytest.mark.db
def test_text_only_endpoint_unchanged_still_works(db, monkeypatch):
    """The original /messages path is untouched and routes via the same turn."""
    captured = {}

    def fake_execute_turn(
        db_,
        organization_id,
        user_id,
        conversation,
        user_message,
        employee=None,
        history_messages=None,
        model=None,
        images=None,
    ):
        captured["text"] = user_message
        return "plain text reply", "general"

    monkeypatch.setattr("app.api.v1.ai_chat.routes.execute_turn", fake_execute_turn)

    org = _org(db)
    user = _user(db, org)
    conv = _conversation(db, org, user)

    try:
        reply = send_message(
            data=MessageCreate(conversation_id=conv.id, content="hello from text"),
            db=db,
            current_user={"sub": str(user.id)},
        )
        assert reply.message == "plain text reply"
        assert captured["text"] == "hello from text"

        from app.models.ai_message import AIMessage

        db.expire_all()
        user_msg = (
            db.query(AIMessage)
            .filter(
                AIMessage.conversation_id == conv.id,
                AIMessage.role == "user",
            )
            .first()
        )
        assert user_msg.message == "hello from text"
        # text path leaves no voice marker
        assert user_msg.message_metadata is None
    finally:
        _teardown(db, org)


def test_voice_route_registered_without_touching_text_route():
    voice_paths = [r.path for r in router.routes if r.path.endswith("/messages/voice")]
    text_paths = [r.path for r in router.routes if r.path == "/ai-chat/messages"]
    assert voice_paths == ["/ai-chat/messages/voice"]
    assert text_paths  # text route still registered as before