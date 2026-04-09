from typing import List, Optional

from pydantic import BaseModel, Field


class InputTriageResult(BaseModel):
    input_type: str
    reasoning: str
    rephrased_question: str = ""


class EvaluationResult(BaseModel):
    score: int = Field(ge=1, le=10)
    feedback: str
    needs_clarification: bool
    clarification_question: str = ""

    answer_quality: str = "partial"  # strong, partial, vague, irrelevant, no_answer
    relevance_score: int = Field(default=5, ge=1, le=10)
    specificity_score: int = Field(default=5, ge=1, le=10)
    evidence_score: int = Field(default=5, ge=1, le=10)

    strengths: List[str] = []
    missing_dimensions: List[str] = []


class StartInterviewResponse(BaseModel):
    conversation_id: str
    skill: Optional[str]
    stage: str
    message: str
    prompt_version: Optional[str]


class RespondRequest(BaseModel):
    answer: str


class RespondResponse(BaseModel):
    conversation_id: str
    stage: str
    message: str
    completed: bool


class MessageResponse(BaseModel):
    role: str
    content: str
    question_index: Optional[int]
    created_at: str


class ConversationResponse(BaseModel):
    conversation_id: str
    skill: Optional[str]
    status: str
    stage: str
    prompt_version: Optional[str]
    created_at: str
    completed_at: Optional[str]
    messages: List[MessageResponse]