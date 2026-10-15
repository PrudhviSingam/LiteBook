from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey
from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class AssistantConversation(Base):
    __tablename__ = "assistant_conversations"

    id = Column(String(100), primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    title = Column(String(255), default="Financial Assistant Conversation", nullable=False)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class AssistantMessage(Base):
    __tablename__ = "assistant_messages"

    id = Column(String(100), primary_key=True, index=True)
    conversation_id = Column(String(100), ForeignKey("assistant_conversations.id", ondelete="CASCADE"), nullable=False, index=True)

    role = Column(String(20), nullable=False)  # "user", "assistant", "system"
    content = Column(Text, nullable=False)
    metadata_json = Column(Text, default="{}", nullable=False)

    created_at = Column(DateTime, default=utcnow, nullable=False)


class AssistantFileContext(Base):
    __tablename__ = "assistant_file_contexts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String(100), ForeignKey("assistant_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)

    created_at = Column(DateTime, default=utcnow, nullable=False)
