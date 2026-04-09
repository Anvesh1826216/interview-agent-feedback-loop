from enum import Enum

class InterviewStage(str, Enum):
    START = "start"
    SELECT_SKILL = "select_skill"
    ASK_QUESTION = "ask_question"
    WAIT_FOR_ANSWER = "wait_for_answer"
    TRIAGE_INPUT = "triage_input"
    REPEAT_QUESTION = "repeat_question"
    REPHRASE_QUESTION = "rephrase_question"
    EVALUATE_ANSWER = "evaluate_answer"
    CLARIFY = "clarify"
    NEXT_QUESTION = "next_question"
    WRAP_UP = "wrap_up"
    END = "end"