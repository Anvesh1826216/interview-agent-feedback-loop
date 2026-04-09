from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

from .enums import InterviewStage


@dataclass
class InterviewState:
    conversation_id: str
    stage: InterviewStage

    skill: Optional[str] = None
    question_index: int = 0
    questions: List[dict] = field(default_factory=list)

    current_question: Optional[str] = None
    current_expected_dimensions: List[str] = field(default_factory=list)

    answers: List[str] = field(default_factory=list)
    evaluations: List[dict] = field(default_factory=list)

    latest_user_input: Optional[str] = None
    last_triage: Dict = field(default_factory=dict)

    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    clarification_attempts: int = 0
    max_clarification_attempts: int = 1

    repeat_requests_for_current_question: int = 0
    rephrase_requests_for_current_question: int = 0
    non_answer_attempts_for_current_question: int = 0
    max_repair_attempts_per_question: int = 2

    prompt_version: str = "v1"
    status: str = "ongoing"

    def to_dict(self) -> dict:
        data = asdict(self)
        data["stage"] = self.stage.value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "InterviewState":
        data = data.copy()
        data["stage"] = InterviewStage(data["stage"])
        return cls(**data)