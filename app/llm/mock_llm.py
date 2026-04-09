import re

from app.agent.schemas import EvaluationResult, InputTriageResult


class MockLLMService:
    def triage_input(
        self,
        question: str,
        user_input: str,
        skill: str,
    ) -> InputTriageResult:
        text = user_input.strip().lower()

        if any(x in text for x in ["repeat", "say that again"]):
            return InputTriageResult(
                input_type="repeat_request",
                reasoning="Detected repeat request.",
                rephrased_question="",
            )

        if any(x in text for x in ["internet", "connection", "audio", "unstable"]):
            return InputTriageResult(
                input_type="temporary_issue",
                reasoning="Detected temporary issue.",
                rephrased_question="",
            )

        if any(x in text for x in ["what do you mean", "can you explain", "rephrase"]):
            return InputTriageResult(
                input_type="clarify_question",
                reasoning="Detected clarification request.",
                rephrased_question=self._rule_based_rephrase(question, skill),
            )

        if text in {"i don't know", "not sure", "pass", "skip"}:
            return InputTriageResult(
                input_type="off_topic_or_no_answer",
                reasoning="Detected no-answer.",
                rephrased_question="",
            )

        return InputTriageResult(
            input_type="direct_answer",
            reasoning="Treating as direct answer.",
            rephrased_question="",
        )
    
    def generate_prompt_suggestions(self, feedback_summary: dict) -> dict:
        return {
            "analysis_summary": (
                "Feedback suggests that the agent would benefit from stronger rubric-based "
                "evaluation and more targeted clarification prompts."
            ),
            "suggestions": [
                "Require clarification questions to target the most important missing dimensions.",
                "Avoid rewarding vague project context unless it answers the actual question.",
                "Strengthen evaluation criteria for relevance, specificity, and evidence."
            ],
            "draft_evaluation_prompt": (
                "You are an interview evaluator for a senior-level technical interview.\n\n"
                "Assess each answer using a structured rubric. A strong answer should be relevant, "
                "specific, supported by concrete examples, and should cover the key expected dimensions "
                "for the question. Do not over-reward partial project context if it does not answer the question. "
                "When clarification is needed, ask for the most important missing dimensions."
            ),
            "draft_clarification_rule": (
                "Ask at most one clarification question per interview question. Clarification should focus "
                "on the most important missing dimensions, such as candidate actions, technical reasoning, "
                "challenge context, and outcome. Avoid generic follow-ups like 'Can you elaborate?'."
            ),
        }
    
    def evaluate_answer(
        self,
        question: str,
        answer: str,
        skill: str,
        prompt_text: str,
        expected_dimensions: list[str],
    ) -> EvaluationResult:
        answer_text = answer.strip()

        if len(answer_text) < 20:
            return EvaluationResult(
                score=3,
                feedback="The answer is too brief and misses important detail.",
                needs_clarification=True,
                clarification_question="Can you provide a specific example, what you did, and what happened in the end?",
                answer_quality="vague",
                relevance_score=5,
                specificity_score=2,
                evidence_score=2,
                strengths=[],
                missing_dimensions=expected_dimensions[:3],
            )

        if re.search(r"\b(FastAPI|SQLite|FSM|backend|API)\b", answer_text, re.IGNORECASE):
            return EvaluationResult(
                score=6,
                feedback="The answer gives technical context, but it does not fully explain the challenge, the candidate’s actions, and the outcome.",
                needs_clarification=True,
                clarification_question="Can you explain what the challenge was, what you specifically did, and what outcome your approach produced?",
                answer_quality="partial",
                relevance_score=6,
                specificity_score=5,
                evidence_score=4,
                strengths=["Relevant technical context"],
                missing_dimensions=["candidate actions", "outcome"],
            )

        return EvaluationResult(
            score=8,
            feedback="The answer is relevant and reasonably detailed.",
            needs_clarification=False,
            clarification_question="",
            answer_quality="strong",
            relevance_score=8,
            specificity_score=8,
            evidence_score=7,
            strengths=["Relevant answer", "Reasonable detail"],
            missing_dimensions=[],
        )

    @staticmethod
    def _rule_based_rephrase(question: str, skill: str) -> str:
        q = question.lower()

        if skill == "Collaboration & Teamwork" and "difficult teammate" in q:
            return (
                "By 'difficult teammate,' I mean someone whose communication style, work style, "
                "or technical opinions created friction. Can you describe one such situation and how you handled it?"
            )

        if skill == "Problem Solving" and "large ambiguous task" in q:
            return (
                "Think about a task where the goal was not fully clear at first. "
                "How would you organize it into smaller, manageable steps?"
            )

        if skill == "Communication" and "non-technical stakeholder" in q:
            return (
                "How would you explain a technical idea to someone without a technical background so they can still understand it?"
            )

        return f"Let me restate it more simply: {question}"