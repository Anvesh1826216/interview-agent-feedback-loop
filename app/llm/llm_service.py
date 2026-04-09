import json
import os
import time
import re
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from app.agent.exceptions import LLMUnavailableError
from app.agent.schemas import EvaluationResult, InputTriageResult

load_dotenv()


class LLMService:
    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set.")

        self.client = OpenAI(api_key=api_key)
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.timeout_seconds = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "20"))
        self.max_retries = int(os.getenv("OPENAI_MAX_RETRIES", "2"))

    def _chat_completion(self, messages, response_format=None, temperature=0.2):
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                kwargs = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "timeout": self.timeout_seconds,
                }
                if response_format is not None:
                    kwargs["response_format"] = response_format

                return self.client.chat.completions.create(**kwargs)

            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    time.sleep(0.75 * (attempt + 1))
                else:
                    raise LLMUnavailableError(str(last_error)) from last_error

    def triage_input(
        self,
        question: str,
        user_input: str,
        skill: str,
    ) -> InputTriageResult:
        normalized = (user_input or "").strip().lower()

        if self._looks_like_repeat_request(normalized):
            return InputTriageResult(
                input_type="repeat_request",
                reasoning="Candidate asked to repeat the question.",
                rephrased_question="",
            )

        if self._looks_like_temporary_issue(normalized):
            return InputTriageResult(
                input_type="temporary_issue",
                reasoning="Candidate mentioned a temporary communication or connection issue.",
                rephrased_question="",
            )

        if self._looks_like_question_clarification_request(normalized):
            return InputTriageResult(
                input_type="clarify_question",
                reasoning="Candidate appears to want the question rephrased or explained.",
                rephrased_question=self.rephrase_question(question, skill),
            )

        if self._looks_like_no_answer(normalized):
            return InputTriageResult(
                input_type="off_topic_or_no_answer",
                reasoning="Candidate did not provide a meaningful answer.",
                rephrased_question="",
            )

        system_prompt = (
            "You classify interview candidate messages. "
            "Return valid JSON only."
        )

        user_prompt = f"""
Question: {question}
Skill: {skill}
Candidate Message: {user_input}

Classify the candidate message into exactly one of:
- direct_answer
- repeat_request
- clarify_question
- temporary_issue
- off_topic_or_no_answer

Return JSON:
{{
  "input_type": "direct_answer",
  "reasoning": "short reason",
  "rephrased_question": ""
}}

Rules:
- repeat_request: candidate asks to hear the same question again
- clarify_question: candidate wants the question explained differently
- temporary_issue: internet/audio/connection issue
- off_topic_or_no_answer: no real answer attempt
- direct_answer: actual answer attempt
- if clarify_question, provide a short rephrased version
"""

        try:
            response = self._chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            )

            content = response.choices[0].message.content or "{}"
            parsed = json.loads(content)

            result = InputTriageResult(
                input_type=str(parsed.get("input_type", "direct_answer")),
                reasoning=str(parsed.get("reasoning", "")),
                rephrased_question=str(parsed.get("rephrased_question", "")),
            )

            if result.input_type not in {
                "direct_answer",
                "repeat_request",
                "clarify_question",
                "temporary_issue",
                "off_topic_or_no_answer",
            }:
                result.input_type = "direct_answer"

            if result.input_type == "clarify_question" and not result.rephrased_question.strip():
                result.rephrased_question = self.rephrase_question(question, skill)

            return result

        except Exception:
            return InputTriageResult(
                input_type="direct_answer",
                reasoning="Fallback classification due to LLM issue.",
                rephrased_question="",
            )

    def rephrase_question(self, question: str, skill: str) -> str:
        fallback = self._rule_based_rephrase(question, skill)

        system_prompt = (
            "You help rephrase interview questions clearly. "
            "Return plain text only. "
            "Do not answer the question. "
            "Keep it to 1-2 sentences."
        )

        user_prompt = f"""
Skill: {skill}
Original question: {question}

Rephrase the question so it is easier to understand.
If there is an abstract term, briefly explain it in context.
"""

        try:
            response = self._chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
            )

            content = response.choices[0].message.content
            if content and content.strip():
                return content.strip()

            return fallback
        except Exception:
            return fallback
        
    def generate_prompt_suggestions(self, feedback_summary: dict) -> dict:
        system_prompt = (
            "You are an expert prompt engineer helping improve an interview agent.\n"
            "You are given aggregated human feedback about completed interviews.\n"
            "Your task is to suggest how to improve the interview agent prompts.\n"
            "Return valid JSON only.\n"
        )

        user_prompt = f"""
Here is the aggregated feedback summary for the interview system:

{json.dumps(feedback_summary, indent=2)}

Return JSON with exactly these keys:
{{
  "analysis_summary": "short paragraph",
  "suggestions": ["suggestion 1", "suggestion 2", "suggestion 3"],
  "draft_evaluation_prompt": "full improved evaluation prompt text",
  "draft_clarification_rule": "full improved clarification rule text"
}}

Rules:
- analysis_summary should explain the main quality issues seen in feedback
- suggestions should be concise and actionable
- draft_evaluation_prompt should improve the evaluator behavior based on the feedback
- draft_clarification_rule should improve follow-up question quality based on the feedback
- do not auto-activate anything
- keep the design human-in-the-loop
- make the drafts suitable for a senior-level technical interview agent
"""

        try:
            response = self._chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
            )

            content = response.choices[0].message.content or "{}"
            parsed = json.loads(content)

            analysis_summary = str(parsed.get("analysis_summary", "")).strip()
            suggestions = parsed.get("suggestions", [])
            draft_evaluation_prompt = str(parsed.get("draft_evaluation_prompt", "")).strip()
            draft_clarification_rule = str(parsed.get("draft_clarification_rule", "")).strip()

            if not isinstance(suggestions, list):
                suggestions = []

            suggestions = [str(x).strip() for x in suggestions if str(x).strip()]

            return {
                "analysis_summary": analysis_summary,
                "suggestions": suggestions,
                "draft_evaluation_prompt": draft_evaluation_prompt,
                "draft_clarification_rule": draft_clarification_rule,
            }

        except Exception:
            return {
                "analysis_summary": "The system could not generate LLM-based prompt suggestions at this time.",
                "suggestions": [
                    "Review the most common flags and strengthen the evaluation rubric accordingly.",
                    "Make clarification questions more targeted to missing dimensions.",
                    "Avoid rewarding vague project context unless it directly answers the question."
                ],
                "draft_evaluation_prompt": "",
                "draft_clarification_rule": "",
            }
    
    def evaluate_answer(
        self,
        question: str,
        answer: str,
        skill: str,
        prompt_text: str,
        expected_dimensions: list[str],
    ) -> EvaluationResult:
        system_prompt = (
            "You are an expert structured interview evaluator. "
            "Return valid JSON only."
        )

        dims_text = ", ".join(expected_dimensions) if expected_dimensions else "relevance, specificity, evidence, completeness"

        user_prompt = f"""
{prompt_text}

Skill: {skill}
Question: {question}
Candidate Answer: {answer}

Expected dimensions for a strong answer:
{dims_text}

Return JSON with exactly these keys:
{{
  "score": 1,
  "feedback": "brief evaluator feedback",
  "needs_clarification": false,
  "clarification_question": "",
  "answer_quality": "partial",
  "relevance_score": 1,
  "specificity_score": 1,
  "evidence_score": 1,
  "strengths": [],
  "missing_dimensions": []
}}
"""

        try:
            response = self._chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )

            content = response.choices[0].message.content
            if not content:
                raise ValueError("Model returned empty content.")

            parsed: dict[str, Any] = json.loads(content)

            return EvaluationResult(
                score=max(1, min(10, int(parsed.get("score", 5)))),
                feedback=str(parsed.get("feedback", "Evaluation completed.")),
                needs_clarification=bool(parsed.get("needs_clarification", False)),
                clarification_question=str(parsed.get("clarification_question", "")),
                answer_quality=str(parsed.get("answer_quality", "partial")),
                relevance_score=max(1, min(10, int(parsed.get("relevance_score", 5)))),
                specificity_score=max(1, min(10, int(parsed.get("specificity_score", 5)))),
                evidence_score=max(1, min(10, int(parsed.get("evidence_score", 5)))),
                strengths=parsed.get("strengths", []) if isinstance(parsed.get("strengths", []), list) else [],
                missing_dimensions=parsed.get("missing_dimensions", []) if isinstance(parsed.get("missing_dimensions", []), list) else [],
            )

        except Exception:
            return EvaluationResult(
                score=5,
                feedback="The system could not evaluate the answer reliably, so it is using a safe fallback.",
                needs_clarification=True,
                clarification_question="Could you answer the question with a specific example, your actions, and the outcome?",
                answer_quality="partial",
                relevance_score=5,
                specificity_score=5,
                evidence_score=5,
                strengths=[],
                missing_dimensions=expected_dimensions[:3],
            )

    @staticmethod
    def _normalize_score(score: Any) -> int:
        try:
            value = int(score)
        except (TypeError, ValueError):
            value = 5
        return max(1, min(10, value))

    @staticmethod
    def _looks_like_repeat_request(text: str) -> bool:
        patterns = [
            r"\bcan you repeat\b",
            r"\brepeat the question\b",
            r"\bsay that again\b",
            r"\bcould you repeat\b",
            r"\bplease repeat\b",
            r"\bi did not catch that\b",
        ]
        return any(re.search(p, text) for p in patterns)

    @staticmethod
    def _looks_like_temporary_issue(text: str) -> bool:
        patterns = [
            r"\binternet\b",
            r"\bconnection\b",
            r"\bnetwork\b",
            r"\baudio\b",
            r"\bvoice\b",
            r"\bmic\b",
            r"\bcan.?t hear\b",
            r"\bunsteady\b",
            r"\bunstable\b",
        ]
        return any(re.search(p, text) for p in patterns)

    @staticmethod
    def _looks_like_question_clarification_request(text: str) -> bool:
        patterns = [
            r"\bwhat do you mean\b",
            r"\bcan you explain\b",
            r"\bi don.?t understand\b",
            r"\bwhat does .* mean\b",
            r"\bcan you rephrase\b",
            r"\bwhat do you mean by\b",
        ]
        return any(re.search(p, text) for p in patterns)

    @staticmethod
    def _looks_like_no_answer(text: str) -> bool:
        patterns = [
            r"^i don.?t know$",
            r"^not sure$",
            r"^no idea$",
            r"^skip$",
            r"^pass$",
        ]
        return any(re.search(p, text) for p in patterns)

    @staticmethod
    def _rule_based_rephrase(question: str, skill: str) -> str:
        q = question.lower()

        if skill == "Collaboration & Teamwork":
            if "difficult teammate" in q:
                return (
                    "By 'difficult teammate,' I mean someone whose communication style, work style, "
                    "or technical decisions created friction or disagreement. Can you describe one such situation and how you handled it?"
                )
            if "disagreement on the technical direction" in q:
                return (
                    "Think of a time when team members disagreed about how to build or design something. "
                    "How did you help the team discuss it and move forward?"
                )
            if "helped a teammate succeed" in q:
                return (
                    "Can you describe a situation where you supported a teammate in a meaningful way and helped them get a good result?"
                )

        if skill == "Problem Solving":
            if "difficult technical problem" in q:
                return (
                    "Think of a challenging technical issue you faced. What was the problem, how did you approach it, and what happened in the end?"
                )
            if "large ambiguous task" in q:
                return (
                    "How do you handle a task when the goal is not fully clear at the start? "
                    "How do you organize it into smaller, manageable steps?"
                )
            if "first solution did not work" in q:
                return (
                    "Can you describe a time when your first approach failed, and explain what you changed afterward?"
                )

        if skill == "Communication":
            if "non-technical stakeholder" in q:
                return (
                    "How would you explain something technical to someone without a technical background so they can still understand it?"
                )
            if "miscommunication caused a problem" in q:
                return (
                    "Can you describe a situation where poor communication caused an issue, and explain how you fixed it?"
                )
            if "written technical updates" in q:
                return (
                    "How do you make your written project or technical updates easy for others to understand and useful to them?"
                )

        return f"Let me restate it more simply: {question}"