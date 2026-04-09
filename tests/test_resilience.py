
import uuid

import pytest

from app.agent.enums import InterviewStage
from app.agent.exceptions import InvalidStateError, MissingUserInputError
from app.agent.fsm import InterviewFSM
from app.agent.schemas import EvaluationResult, InputTriageResult
from app.agent.state import InterviewState


class FakePromptLoader:
    def get_active_prompts(self, db=None):
        return {
            "version": "test-v1",
            "evaluation_prompt": "Evaluate safely.",
            "clarification_rule": "Ask one clarification.",
        }


class FailingLLM:
    def triage_input(self, question, user_input, skill):
        raise Exception("Simulated triage failure")

    def evaluate_answer(self, question, answer, skill, prompt_text, expected_dimensions):
        return EvaluationResult(
            score=5,
            feedback="Fallback evaluation used.",
            needs_clarification=True,
            clarification_question="Please provide a specific example, your actions, and the outcome.",
            answer_quality="partial",
            relevance_score=5,
            specificity_score=5,
            evidence_score=5,
            strengths=[],
            missing_dimensions=expected_dimensions[:3],
        )


class SafeLLM:
    def triage_input(self, question, user_input, skill):
        return InputTriageResult(
            input_type="direct_answer",
            reasoning="direct answer",
            rephrased_question="",
        )

    def evaluate_answer(self, question, answer, skill, prompt_text, expected_dimensions):
        return EvaluationResult(
            score=8,
            feedback="The answer is relevant and reasonably detailed.",
            needs_clarification=False,
            clarification_question="",
            answer_quality="strong",
            relevance_score=8,
            specificity_score=8,
            evidence_score=8,
            strengths=["Relevant answer"],
            missing_dimensions=[],
        )


def make_state():
    return InterviewState(
        conversation_id=str(uuid.uuid4()),
        stage=InterviewStage.WAIT_FOR_ANSWER,
        skill="Problem Solving",
        questions=[
            {
                "question": "Tell me about a difficult technical problem you solved. How did you approach it?",
                "expected_dimensions": [
                    "problem context",
                    "approach",
                    "technical steps",
                    "decision-making",
                    "result",
                ],
            }
        ],
        current_question="Tell me about a difficult technical problem you solved. How did you approach it?",
        current_expected_dimensions=[
            "problem context",
            "approach",
            "technical steps",
            "decision-making",
            "result",
        ],
        prompt_version="test-v1",
    )


def test_blank_input_is_handled_gracefully():
    fsm = InterviewFSM(llm_service=SafeLLM(), prompt_loader=FakePromptLoader())
    state = make_state()

    state, _ = fsm.step(state, user_input="   ")
    state, msg = fsm.step(state)

    assert state.stage == InterviewStage.WAIT_FOR_ANSWER
    assert "actual answer" in msg.lower() or "please answer" in msg.lower()


def test_missing_input_raises_meaningful_error():
    fsm = InterviewFSM(llm_service=SafeLLM(), prompt_loader=FakePromptLoader())
    state = make_state()

    with pytest.raises(MissingUserInputError):
        fsm.step(state, user_input=None)


def test_invalid_state_raises_error():
    fsm = InterviewFSM(llm_service=SafeLLM(), prompt_loader=FakePromptLoader())
    state = make_state()
    state.stage = "bad_state"  # intentionally invalid

    with pytest.raises(InvalidStateError):
        fsm.step(state)


def test_safe_path_with_normal_answer():
    fsm = InterviewFSM(llm_service=SafeLLM(), prompt_loader=FakePromptLoader())
    state = make_state()

    state, _ = fsm.step(
        state,
        user_input="I solved a backend scaling issue by profiling queries and optimizing caching."
    )
    state, _ = fsm.step(state)   # triage
    state, feedback = fsm.step(state)  # evaluate

    assert "relevant" in feedback.lower()
    assert state.stage == InterviewStage.NEXT_QUESTION

