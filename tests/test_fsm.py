from app.agent.enums import InterviewStage
from app.agent.fsm import InterviewFSM
from app.agent.state import InterviewState
from app.llm.mock_llm import MockLLMService


class FakePromptLoader:
    def get_active_prompts(self, db=None):
        return {
            "version": "test-v1",
            "evaluation_prompt": "Evaluate safely.",
            "clarification_rule": "Ask one clarification.",
        }


def build_fsm():
    return InterviewFSM(MockLLMService(), FakePromptLoader())


def test_start_moves_to_select_skill():
    fsm = build_fsm()
    state = InterviewState(conversation_id="1", stage=InterviewStage.START)

    state, _ = fsm.step(state)

    assert state.stage == InterviewStage.SELECT_SKILL


def test_select_skill_sets_questions_and_prompt_version():
    fsm = build_fsm()
    state = InterviewState(conversation_id="1", stage=InterviewStage.SELECT_SKILL)

    state, _ = fsm.step(state)

    assert state.skill is not None
    assert len(state.questions) == 3
    assert state.prompt_version == "test-v1"
    assert state.stage == InterviewStage.ASK_QUESTION


def test_short_answer_triggers_clarification():
    fsm = build_fsm()
    state = InterviewState(conversation_id="1", stage=InterviewStage.SELECT_SKILL)

    state, _ = fsm.step(state)                    # select skill
    state, _ = fsm.step(state)                    # ask question
    state, _ = fsm.step(state, user_input="yes")  # wait_for_answer -> triage_input
    state, _ = fsm.step(state)                    # triage_input -> evaluate_answer
    state, _ = fsm.step(state)                    # evaluate_answer -> feedback

    assert state.stage == InterviewStage.CLARIFY


def test_long_answer_moves_forward():
    fsm = build_fsm()
    state = InterviewState(conversation_id="1", stage=InterviewStage.SELECT_SKILL)

    state, _ = fsm.step(state)  # select skill
    state, _ = fsm.step(state)  # ask question
    state, _ = fsm.step(
        state,
        user_input=(
            "I worked on a difficult migration project, broke it into phases, "
            "identified risks, and validated each phase before rollout."
        ),
    )
    state, _ = fsm.step(state)  # triage
    state, _ = fsm.step(state)  # evaluate

    assert state.stage == InterviewStage.NEXT_QUESTION