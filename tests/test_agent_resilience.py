import uuid

from app.agent.enums import InterviewStage
from app.agent.fsm import InterviewFSM
from app.agent.question_bank import QUESTION_BANK
from app.agent.state import InterviewState
from app.llm.mock_llm import MockLLMService


class FakePromptLoader:
    def get_active_prompts(self, db=None):
        return {
            "version": "test-v1",
            "evaluation_prompt": "Evaluate carefully and ask targeted clarifications.",
            "clarification_rule": "Ask at most one clarification.",
        }


def build_fsm():
    return InterviewFSM(llm_service=MockLLMService(), prompt_loader=FakePromptLoader())


def make_state(skill: str):
    return InterviewState(
        conversation_id=str(uuid.uuid4()),
        stage=InterviewStage.ASK_QUESTION,
        skill=skill,
        questions=QUESTION_BANK[skill],
        prompt_version="test-v1",
    )


def step_until_message(fsm, state, max_steps=6):
    msg = ""
    for _ in range(max_steps):
        state, msg = fsm.step(state)
        if msg and msg.strip():
            return state, msg
    return state, msg


# -------------------------
# Problem Solving tests
# -------------------------
def test_problem_solving_repeat_request():
    fsm = build_fsm()
    state = make_state("Problem Solving")

    state, msg = fsm.step(state)
    assert "difficult technical problem" in msg.lower()

    state, _ = fsm.step(state, user_input="can you repeat the question?")
    state, msg = step_until_message(fsm, state)

    assert "question again" in msg.lower() or "repeat" in msg.lower()
    assert state.stage == InterviewStage.WAIT_FOR_ANSWER
    assert state.question_index == 0


def test_problem_solving_rephrase_request():
    fsm = build_fsm()
    state = make_state("Problem Solving")

    state, _ = fsm.step(state)
    state, _ = fsm.step(state, user_input="what do you mean by ambiguous?")
    state, msg = step_until_message(fsm, state)

    assert "another way" in msg.lower() or "restated" in msg.lower()
    assert state.stage == InterviewStage.WAIT_FOR_ANSWER


def test_problem_solving_partial_answer_gets_clarification():
    fsm = build_fsm()
    state = make_state("Problem Solving")

    state, _ = fsm.step(state)
    state, _ = fsm.step(state, user_input="It was during my FastAPI project.")
    state, _ = fsm.step(state)   # triage
    state, feedback = fsm.step(state)  # evaluate

    assert "technical context" in feedback.lower() or "does not fully explain" in feedback.lower()
    assert state.stage == InterviewStage.CLARIFY

    state, clarification = fsm.step(state)
    assert "what you specifically did" in clarification.lower() or "outcome" in clarification.lower()


# -------------------------
# Communication tests
# -------------------------
def test_communication_repeat_request():
    fsm = build_fsm()
    state = make_state("Communication")

    state, msg = fsm.step(state)
    assert "non-technical stakeholder" in msg.lower()

    state, _ = fsm.step(state, user_input="can you repeat the question?")
    state, msg = step_until_message(fsm, state)

    assert "question again" in msg.lower() or "repeat" in msg.lower()
    assert state.question_index == 0


def test_communication_no_answer_handling():
    fsm = build_fsm()
    state = make_state("Communication")

    state, _ = fsm.step(state)
    state, _ = fsm.step(state, user_input="I don't know")
    state, msg = step_until_message(fsm, state)

    assert "didn't think i received an actual answer" in msg.lower() or "please answer this question" in msg.lower()
    assert state.stage == InterviewStage.WAIT_FOR_ANSWER


def test_communication_strong_answer_moves_forward():
    fsm = build_fsm()
    state = make_state("Communication")

    state, _ = fsm.step(state)
    strong_answer = (
        "I would explain the concept in simpler terms, avoid jargon, use a relatable example, "
        "and then check whether the stakeholder understood the main point."
    )
    state, _ = fsm.step(state, user_input=strong_answer)
    state, _ = fsm.step(state)   # triage
    state, feedback = fsm.step(state)  # evaluate

    assert "relevant" in feedback.lower() or "reasonably detailed" in feedback.lower()
    assert state.stage == InterviewStage.NEXT_QUESTION


# -------------------------
# Collaboration & Teamwork tests
# -------------------------
def test_collaboration_rephrase_is_meaningful():
    fsm = build_fsm()
    state = make_state("Collaboration & Teamwork")

    state, _ = fsm.step(state)
    state, _ = fsm.step(state, user_input="what do you mean by difficult?")
    state, msg = step_until_message(fsm, state)

    assert (
        "communication style" in msg.lower()
        or "friction" in msg.lower()
        or "disagreement" in msg.lower()
    )
    assert state.stage == InterviewStage.WAIT_FOR_ANSWER


def test_collaboration_temporary_issue_does_not_penalize():
    fsm = build_fsm()
    state = make_state("Collaboration & Teamwork")

    state, _ = fsm.step(state)
    state, _ = fsm.step(state, user_input="my internet is unstable, say that again please")
    state, msg = step_until_message(fsm, state)

    assert "repeat" in msg.lower() or "again" in msg.lower()
    assert state.question_index == 0
    assert state.stage == InterviewStage.WAIT_FOR_ANSWER


def test_collaboration_partial_answer_gets_targeted_followup():
    fsm = build_fsm()
    state = make_state("Collaboration & Teamwork")

    state, _ = fsm.step(state)
    state, _ = fsm.step(state, user_input="It was during my FastAPI project.")
    state, _ = fsm.step(state)   # triage
    state, feedback = fsm.step(state)  # evaluate

    assert "does not fully explain" in feedback.lower() or "challenge" in feedback.lower()
    assert state.stage == InterviewStage.CLARIFY

    state, clarification = fsm.step(state)
    assert (
        "challenge" in clarification.lower()
        or "what you specifically did" in clarification.lower()
        or "outcome" in clarification.lower()
    )


# -------------------------
# Resilience / state tests
# -------------------------
def test_empty_input_does_not_crash():
    fsm = build_fsm()
    state = make_state("Problem Solving")

    state, _ = fsm.step(state)
    state, _ = fsm.step(state, user_input="   ")
    state, msg = step_until_message(fsm, state)

    assert state.stage == InterviewStage.WAIT_FOR_ANSWER
    assert "please answer this question" in msg.lower() or "actual answer" in msg.lower()


def test_interview_reaches_end_cleanly():
    fsm = build_fsm()
    state = make_state("Problem Solving")

    for _ in range(3):
        state, _ = fsm.step(state)  # ask
        state, _ = fsm.step(
            state,
            user_input="I handled a technical problem by breaking it down, testing hypotheses, and validating the outcome."
        )
        state, _ = fsm.step(state)  # triage
        state, _ = fsm.step(state)  # evaluate

        if state.stage == InterviewStage.CLARIFY:
            state, _ = fsm.step(state)
            state, _ = fsm.step(
                state,
                user_input="I identified the issue, explained my actions, and achieved a good result."
            )
            state, _ = fsm.step(state)
            state, _ = fsm.step(state)

        state, _ = fsm.step(state)  # next question / wrap-up

    if state.stage == InterviewStage.WRAP_UP:
        state, final_msg = fsm.step(state)
        assert "interview complete" in final_msg.lower()

    assert state.stage == InterviewStage.END