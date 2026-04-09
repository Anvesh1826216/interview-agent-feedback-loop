import json
from collections import Counter, defaultdict
class PromptSuggestionService:
    def __init__(self, llm_service):
        self.llm = llm_service
    def build_feedback_summary(self, feedback_rows, conversations):
        conversation_map = {c.id: c for c in conversations}
        total_feedback = len(feedback_rows)
        overall_values = [f.overall_rating for f in feedback_rows if f.overall_rating is not None]
        fairness_values = [f.fairness_rating for f in feedback_rows if f.fairness_rating is not None]
        relevance_values = [f.relevance_rating for f in feedback_rows if f.relevance_rating is not None]
        def avg(values):
            return round(sum(values) / len(values), 2) if values else 0.0
        skill_counts = defaultdict(int)
        skill_overall = defaultdict(list)
        prompt_counts = defaultdict(int)
        prompt_overall = defaultdict(list)
        flag_counter = Counter()
        comments = []
        for f in feedback_rows:
            conv = conversation_map.get(f.conversation_id)
            skill = conv.skill if conv and conv.skill else "Unknown"
            prompt_version = conv.prompt_version if conv and conv.prompt_version else "Unknown"
            skill_counts[skill] += 1
            prompt_counts[prompt_version] += 1
            if f.overall_rating is not None:
                skill_overall[skill].append(f.overall_rating)
                prompt_overall[prompt_version].append(f.overall_rating)
            try:
                parsed_flags = json.loads(f.flags) if f.flags else []
                if isinstance(parsed_flags, list):
                    for flag in parsed_flags:
                        if flag:
                            flag_counter[str(flag).strip()] += 1
                elif parsed_flags:
                    flag_counter[str(parsed_flags).strip()] += 1
            except Exception:
                if f.flags:
                    flag_counter[f.flags.strip()] += 1
            if f.comments:
                comments.append(f.comments.strip())
        skill_summary = []
        for skill, count in skill_counts.items():
            skill_summary.append(
                {
                    "skill": skill,
                    "feedback_count": count,
                    "avg_overall": avg(skill_overall[skill]),
                }
            )
        prompt_summary = []
        for version, count in prompt_counts.items():
            prompt_summary.append(
                {
                    "prompt_version": version,
                    "feedback_count": count,
                    "avg_overall": avg(prompt_overall[version]),
                }
            )
        summary = {
            "total_feedback": total_feedback,
            "avg_overall": avg(overall_values),
            "avg_fairness": avg(fairness_values),
            "avg_relevance": avg(relevance_values),
            "skill_summary": sorted(skill_summary, key=lambda x: x["skill"]),
            "prompt_summary": sorted(prompt_summary, key=lambda x: x["prompt_version"]),
            "top_flags": [{"flag": flag, "count": count} for flag, count in flag_counter.most_common(10)],
            "recent_comments": comments[:20],
        }
        return summary
    def generate_prompt_suggestions(self, feedback_summary: dict) -> dict:
        if feedback_summary["total_feedback"] == 0:
            return {
                "analysis_summary": "No feedback is available yet, so no prompt improvement suggestions can be generated.",
                "suggestions": [],
                "draft_evaluation_prompt": "",
                "draft_clarification_rule": "",
            }
        return self.llm.generate_prompt_suggestions(feedback_summary)