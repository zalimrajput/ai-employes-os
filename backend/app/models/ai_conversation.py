from sqlalchemy import Column, String, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class AIConversation(Base):

    __tablename__ = "ai_conversations"


    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default="gen_random_uuid()"
    )


    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False
    )


    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False
    )


    ai_employee_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ai_employees.id"),
        nullable=True
    )

    ai_employee = relationship(
        "AIEmployee",
        foreign_keys=[ai_employee_id],
        lazy="joined",
    )


    title = Column(
        String,
        nullable=True
    )


    status = Column(
        String,
        default="active"
    )


    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )


    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )