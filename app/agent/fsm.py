import random
import re
from .enums import InterviewStage
from .exceptions import InvalidStateError, MissingUserInputError
from .question_bank import QUESTION_BANK
from .state import InterviewState


class InterviewFSM:
    def __init__(self, llm_service, prompt_loader):
        self.llm = llm_service
        self.prompt_loader = prompt_loader

    def step(self, state: InterviewState, db=None, user_input: str | None = None):
        if state.stage == InterviewStage.START:
            return self._handle_start(state)

        if state.stage == InterviewStage.SELECT_SKILL:
            return self._handle_select_skill(state, db)

        if state.stage == InterviewStage.ASK_QUESTION:
            return self._handle_ask_question(state)

        if state.stage == InterviewStage.WAIT_FOR_ANSWER:
            return self._handle_wait_for_answer(state, user_input)

        if state.stage == InterviewStage.TRIAGE_INPUT:
            return self._handle_triage_input(state, db)

        if state.stage == InterviewStage.REPEAT_QUESTION:
            return self._handle_repeat_question(state)

        if state.stage == InterviewStage.REPHRASE_QUESTION:
            return self._handle_rephrase_question(state)

        if state.stage == InterviewStage.EVALUATE_ANSWER:
            return self._handle_evaluate_answer(state, db)

        if state.stage == InterviewStage.CLARIFY:
            return self._handle_clarify(state)

        if state.stage == InterviewStage.NEXT_QUESTION:
            return self._handle_next_question(state)

        if state.stage == InterviewStage.WRAP_UP:
            return self._handle_wrap_up(state)

        if state.stage == InterviewStage.END:
            return state, "Interview already completed."

        raise InvalidStateError(f"Unknown state: {state.stage}")

    def _handle_start(self, state: InterviewState):
        state.stage = InterviewStage.SELECT_SKILL
        return state, "Welcome to the interview."

    def _handle_select_skill(self, state: InterviewState, db):
        state.skill = random.choice(list(QUESTION_BANK.keys()))
        state.questions = QUESTION_BANK[state.skill]

        prompts = self.prompt_loader.get_active_prompts(db)
        state.prompt_version = prompts["version"]

        state.stage = InterviewStage.ASK_QUESTION
        return state, f"Selected skill: {state.skill}"

    def _handle_ask_question(self, state: InterviewState):
        qdata = state.questions[state.question_index]
        state.current_question = qdata["question"]
        state.current_expected_dimensions = qdata.get("expected_dimensions", [])

        state.latest_user_input = None
        state.last_triage = {}
        state.needs_clarification = False
        state.clarification_question = None
        state.clarification_attempts = 0
        state.repeat_requests_for_current_question = 0
        state.rephrase_requests_for_current_question = 0
        state.non_answer_attempts_for_current_question = 0

        state.stage = InterviewStage.WAIT_FOR_ANSWER
        return state, state.current_question

    def _handle_wait_for_answer(self, state: InterviewState, user_input: str | None):
        if user_input is None:
            raise MissingUserInputError("User input is required in WAIT_FOR_ANSWER state.")

        cleaned = user_input.strip()
        if not cleaned:
            state.non_answer_attempts_for_current_question += 1
            state.stage = InterviewStage.REPEAT_QUESTION
            state.last_triage = {
                "input_type": "off_topic_or_no_answer",
                "reasoning": "Empty input received.",
                "rephrased_question": "",
            }
            return state, ""

        state.latest_user_input = cleaned
        state.stage = InterviewStage.TRIAGE_INPUT
        return state, ""

    def _handle_triage_input(self, state: InterviewState, db):
        triage = self.llm.triage_input(
            question=state.current_question,
            user_input=state.latest_user_input or "",
            skill=state.skill or "",
        )
        state.last_triage = triage.model_dump()

        if triage.input_type == "direct_answer":
            state.answers.append(state.latest_user_input or "")
            state.stage = InterviewStage.EVALUATE_ANSWER
            return state, ""

        if triage.input_type in {"repeat_request", "temporary_issue"}:
            state.repeat_requests_for_current_question += 1
            state.stage = InterviewStage.REPEAT_QUESTION
            return state, ""

        if triage.input_type == "clarify_question":
            state.rephrase_requests_for_current_question += 1
            state.stage = InterviewStage.REPHRASE_QUESTION
            return state, ""

        state.non_answer_attempts_for_current_question += 1
        state.stage = InterviewStage.REPEAT_QUESTION
        return state, ""

    def _handle_repeat_question(self, state: InterviewState):
        triage_type = state.last_triage.get("input_type", "")

        if triage_type == "temporary_issue":
            msg = f"No problem — I’ll repeat it clearly.\n\n{state.current_question}"
        elif triage_type == "off_topic_or_no_answer":
            if state.non_answer_attempts_for_current_question <= state.max_repair_attempts_per_question:
                msg = (
                    "I don’t think I received an actual answer yet. "
                    "Please answer this question when you’re ready:\n\n"
                    f"{state.current_question}"
                )
            else:
                msg = (
                    "Let’s try once more. Even a brief real example is fine.\n\n"
                    f"{state.current_question}"
                )
        else:
            msg = f"Of course — here is the question again:\n\n{state.current_question}"

        state.stage = InterviewStage.WAIT_FOR_ANSWER
        return state, msg

    def _handle_rephrase_question(self, state: InterviewState):
        rephrased = self.last_rephrased_question(state)
        msg = f"Sure — here’s the question in another way:\n\n{rephrased}"
        state.stage = InterviewStage.WAIT_FOR_ANSWER
        return state, msg

    def _handle_evaluate_answer(self, state: InterviewState, db):
        prompts = self.prompt_loader.get_active_prompts(db)

        result = self.llm.evaluate_answer(
            question=state.current_question or "",
            answer=state.answers[-1],
            skill=state.skill or "",
            prompt_text=prompts["evaluation_prompt"],
            expected_dimensions=state.current_expected_dimensions,
        )

        state.evaluations.append(result.model_dump())

        if result.answer_quality in {"irrelevant", "no_answer"}:
            if state.non_answer_attempts_for_current_question < state.max_repair_attempts_per_question:
                state.non_answer_attempts_for_current_question += 1
                state.clarification_question = (
                    "I still need a direct answer to the question. "
                    f"Please focus on this:\n\n{state.current_question}"
                )
                state.stage = InterviewStage.CLARIFY
                return state, result.feedback

        if result.needs_clarification and state.clarification_attempts < state.max_clarification_attempts:
            state.needs_clarification = True
            state.clarification_question = result.clarification_question
            state.clarification_attempts += 1
            state.stage = InterviewStage.CLARIFY
            return state, result.feedback

        state.needs_clarification = False
        state.clarification_question = None
        state.stage = InterviewStage.NEXT_QUESTION
        return state, result.feedback

    def _handle_clarify(self, state: InterviewState):
        state.stage = InterviewStage.WAIT_FOR_ANSWER
        return state, state.clarification_question or state.current_question or ""

    def _handle_next_question(self, state: InterviewState):
        state.question_index += 1

        if state.question_index >= 3:
            state.stage = InterviewStage.WRAP_UP
            return state, "That was the last question."

        state.stage = InterviewStage.ASK_QUESTION
        return state, "Let’s move to the next question."

    def _handle_wrap_up(self, state: InterviewState):
        state.status = "completed"
        state.stage = InterviewStage.END
        return state, "Interview complete. Thank you for your time."

    def last_rephrased_question(self, state: InterviewState) -> str:
        rephrased = state.last_triage.get("rephrased_question", "")
        return rephrased if rephrased else (state.current_question or "")