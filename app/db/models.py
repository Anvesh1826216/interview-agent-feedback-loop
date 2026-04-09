from datetime import datetime
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, index=True)
    skill = Column(String, nullable=True)
    status = Column(String, nullable=False, default="ongoing")
    stage = Column(String, nullable=False)
    prompt_version = Column(String, nullable=True)

    state_json = Column(Text, nullable=False)

    created_at = Column(DateTime, default=datetime.now(ZoneInfo("Europe/Rome")).replace(tzinfo=None))
    completed_at = Column(DateTime, nullable=True)

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    feedback_entries = relationship("Feedback", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False, index=True)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    question_index = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.now(ZoneInfo("Europe/Rome")).replace(tzinfo=None))

    conversation = relationship("Conversation", back_populates="messages")


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False, index=True)
    evaluator = Column(String, nullable=True)

    overall_rating = Column(Integer, nullable=True)
    fairness_rating = Column(Integer, nullable=True)
    relevance_rating = Column(Integer, nullable=True)

    flags = Column(Text, nullable=True)
    comments = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.now(ZoneInfo("Europe/Rome")).replace(tzinfo=None))

    conversation = relationship("Conversation", back_populates="feedback_entries")


class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id = Column(Integer, primary_key=True, index=True)
    version = Column(String, unique=True, nullable=False, index=True)
    evaluation_prompt = Column(Text, nullable=False)
    clarification_rule = Column(Text, nullable=True)
    is_active = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.now(ZoneInfo("Europe/Rome")).replace(tzinfo=None))
    
    
class ComparisonFeedback(Base):
    __tablename__ = "comparison_feedback"

    id = Column(Integer, primary_key=True, index=True)

    conversation_a_id = Column(String, ForeignKey("conversations.id"), nullable=False, index=True)
    conversation_b_id = Column(String, ForeignKey("conversations.id"), nullable=False, index=True)

    prompt_version_a = Column(String, nullable=True)
    prompt_version_b = Column(String, nullable=True)

    evaluator = Column(String, nullable=True)
    preference = Column(String, nullable=False)  # "A", "B", "Tie"
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.now(ZoneInfo("Europe/Rome")).replace(tzinfo=None))