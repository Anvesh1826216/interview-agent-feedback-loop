import json
import logging
from collections import Counter, defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.db.models import (
    ComparisonFeedback,
    Conversation,
    Feedback,
    Message,
    PromptVersion,
)
from app.llm.llm_service import LLMService
from app.llm.mock_llm import MockLLMService
from app.prompts.db_loader import DBPromptLoader
from app.services.prompt_suggestion_service import PromptSuggestionService

templates = Jinja2Templates(directory="app/ui/templates")
logger = logging.getLogger(__name__)


def create_admin_routes() -> APIRouter:
    router = APIRouter()
    prompt_loader = DBPromptLoader()
    llm_service = MockLLMService() if settings.USE_MOCK_LLM else LLMService()
    prompt_suggestion_service = PromptSuggestionService(llm_service)

    @router.get("/login", response_class=HTMLResponse)
    def login_page(request: Request, error: str = ""):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": error},
        )

    @router.post("/login")
    def login(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
    ):
        if username == settings.ADMIN_USERNAME and password == settings.ADMIN_PASSWORD:
            request.session["admin_user"] = username
            return RedirectResponse(url="/admin", status_code=303)

        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "Invalid username or password"},
            status_code=401,
        )

    @router.get("/logout")
    def logout(request: Request):
        request.session.clear()
        return RedirectResponse(url="/", status_code=303)

    @router.get("/admin", response_class=HTMLResponse)
    def admin_dashboard(request: Request, db: Session = Depends(get_db)):
        admin_user = request.session.get("admin_user")
        if not admin_user:
            return RedirectResponse(url="/login", status_code=303)

        conversation_count = db.query(Conversation).count()
        message_count = db.query(Message).count()
        feedback_count = db.query(Feedback).count()
        prompt_count = db.query(PromptVersion).count()

        latest_rows = (
            db.query(Conversation)
            .order_by(Conversation.created_at.desc())
            .limit(5)
            .all()
        )

        latest_conversations = []
        for c in latest_rows:
            review_count = db.query(Feedback).filter(Feedback.conversation_id == c.id).count()
            latest_conversations.append(
                {
                    "id": c.id,
                    "skill": c.skill or "-",
                    "status": c.status,
                    "stage": c.stage,
                    "prompt_version": c.prompt_version or "-",
                    "created_at": c.created_at.strftime("%d-%m-%Y %H:%M:%S") if c.created_at else "-",
                    "completed_at": c.completed_at.strftime("%d-%m-%Y %H:%M:%S") if c.completed_at else "-",
                    "reviewed": review_count > 0,
                }
            )

        return templates.TemplateResponse(
            request=request,
            name="admin_dashboard.html",
            context={
                "admin_user": admin_user,
                "conversation_count": conversation_count,
                "message_count": message_count,
                "feedback_count": feedback_count,
                "prompt_count": prompt_count,
                "latest_conversations": latest_conversations,
            },
        )

    @router.get("/admin/conversations", response_class=HTMLResponse)
    def conversations_page(
        request: Request,
        db: Session = Depends(get_db),
        conversation_id: str = "",
        skill: str = "",
        status: str = "",
        reviewed: str = "",
        prompt_version: str = "",
        created_from: str = "",
        created_to: str = "",
    ):
        admin_user = request.session.get("admin_user")
        if not admin_user:
            return RedirectResponse(url="/login", status_code=303)

        message = ""

        query = db.query(Conversation)

        exact_match_exists = None
        if conversation_id.strip():
            exact_match_exists = (
                db.query(Conversation)
                .filter(Conversation.id == conversation_id.strip())
                .first()
            )
            query = query.filter(Conversation.id.contains(conversation_id.strip()))

        if skill:
            query = query.filter(Conversation.skill == skill)

        if status:
            query = query.filter(Conversation.status == status)

        if prompt_version:
            query = query.filter(Conversation.prompt_version == prompt_version)

        if created_from:
            try:
                dt_from = datetime.strptime(created_from, "%Y-%m-%d")
                query = query.filter(Conversation.created_at >= dt_from)
            except ValueError:
                pass

        if created_to:
            try:
                dt_to = datetime.strptime(created_to, "%Y-%m-%d")
                dt_to = dt_to.replace(hour=23, minute=59, second=59)
                query = query.filter(Conversation.created_at <= dt_to)
            except ValueError:
                pass

        rows = query.order_by(Conversation.created_at.desc()).all()

        conversations = []
        for c in rows:
            review_count = db.query(Feedback).filter(Feedback.conversation_id == c.id).count()
            is_reviewed = review_count > 0

            if reviewed == "yes" and not is_reviewed:
                continue
            if reviewed == "no" and is_reviewed:
                continue

            conversations.append(
                {
                    "id": c.id,
                    "skill": c.skill or "-",
                    "status": c.status,
                    "stage": c.stage,
                    "prompt_version": c.prompt_version or "-",
                    "created_at": c.created_at.strftime("%d-%m-%Y %H:%M:%S") if c.created_at else "-",
                    "completed_at": c.completed_at.strftime("%d-%m-%Y %H:%M:%S") if c.completed_at else "-",
                    "reviewed": is_reviewed,
                    "review_count": review_count,
                }
            )

        if conversation_id.strip() and not exact_match_exists:
            message = f"Conversation ID not found: {conversation_id.strip()}"
            logger.warning("Conversation search ID not found: %s", conversation_id.strip())

        available_skills = [
            "Problem Solving",
            "Communication",
            "Collaboration & Teamwork",
        ]

        available_prompt_versions = [
            p[0] for p in db.query(Conversation.prompt_version).distinct().all() if p[0]
        ]

        return templates.TemplateResponse(
            request=request,
            name="conversations.html",
            context={
                "admin_user": admin_user,
                "conversations": conversations,
                "message": message,
                "filters": {
                    "conversation_id": conversation_id,
                    "skill": skill,
                    "status": status,
                    "reviewed": reviewed,
                    "prompt_version": prompt_version,
                    "created_from": created_from,
                    "created_to": created_to,
                },
                "available_skills": available_skills,
                "available_prompt_versions": available_prompt_versions,
            },
        )

    @router.get("/admin/conversations/{conversation_id}", response_class=HTMLResponse)
    def conversation_detail(conversation_id: str, request: Request, db: Session = Depends(get_db)):
        admin_user = request.session.get("admin_user")
        if not admin_user:
            return RedirectResponse(url="/login", status_code=303)

        conversation = (
            db.query(Conversation)
            .filter(Conversation.id == conversation_id)
            .first()
        )

        if not conversation:
            logger.warning("Conversation detail not found: %s", conversation_id)
            return RedirectResponse(url="/admin/conversations", status_code=303)

        message_rows = (
            db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .all()
        )

        messages = [
            {
                "role": m.role,
                "content": m.content,
                "question_index": (m.question_index) if m.question_index is not None else None,
                "created_at": m.created_at.strftime("%d-%m-%Y %H:%M:%S") if m.created_at else "-",
            }
            for m in message_rows
        ]

        feedback_rows = (
            db.query(Feedback)
            .filter(Feedback.conversation_id == conversation_id)
            .order_by(Feedback.created_at.desc())
            .all()
        )

        feedback_entries = []
        for f in feedback_rows:
            try:
                parsed_flags = json.loads(f.flags) if f.flags else []
            except Exception:
                parsed_flags = [f.flags] if f.flags else []

            feedback_entries.append(
                {
                    "id": f.id,
                    "evaluator": f.evaluator or "-",
                    "overall_rating": f.overall_rating,
                    "fairness_rating": f.fairness_rating,
                    "relevance_rating": f.relevance_rating,
                    "flags": parsed_flags,
                    "comments": f.comments or "",
                    "created_at": f.created_at.strftime("%d-%m-%Y %H:%M:%S") if f.created_at else "-",
                }
            )

        try:
            parsed_state = json.loads(conversation.state_json) if conversation.state_json else {}
            state_json_pretty = json.dumps(parsed_state, indent=2)
        except Exception as e:
            state_json_pretty = f"Could not parse state JSON: {str(e)}"

        conversation_data = {
            "id": conversation.id,
            "skill": conversation.skill or "-",
            "status": conversation.status,
            "stage": conversation.stage,
            "prompt_version": conversation.prompt_version or "-",
            "created_at": conversation.created_at.strftime("%d-%m-%Y %H:%M:%S") if conversation.created_at else "-",
            "completed_at": conversation.completed_at.strftime("%d-%m-%Y %H:%M:%S") if conversation.completed_at else "-",
        }

        return templates.TemplateResponse(
            request=request,
            name="conversation_detail.html",
            context={
                "admin_user": admin_user,
                "conversation": conversation_data,
                "messages": messages,
                "state_json_pretty": state_json_pretty,
                "feedback_entries": feedback_entries,
            },
        )

    @router.post("/admin/conversations/{conversation_id}/feedback")
    def submit_feedback(
        conversation_id: str,
        request: Request,
        overall_rating: int = Form(...),
        fairness_rating: int = Form(...),
        relevance_rating: int = Form(...),
        flags: str = Form(""),
        comments: str = Form(""),
        db: Session = Depends(get_db),
    ):
        admin_user = request.session.get("admin_user")
        if not admin_user:
            return RedirectResponse(url="/login", status_code=303)

        conversation = (
            db.query(Conversation)
            .filter(Conversation.id == conversation_id)
            .first()
        )
        if not conversation:
            logger.warning("Feedback submission failed, conversation not found: %s", conversation_id)
            return RedirectResponse(url="/admin/conversations", status_code=303)

        parsed_flags = [flag.strip() for flag in flags.split(",") if flag.strip()]

        feedback = Feedback(
            conversation_id=conversation_id,
            evaluator=admin_user,
            overall_rating=overall_rating,
            fairness_rating=fairness_rating,
            relevance_rating=relevance_rating,
            flags=json.dumps(parsed_flags),
            comments=comments.strip(),
        )

        db.add(feedback)
        db.commit()

        return RedirectResponse(url=f"/admin/conversations/{conversation_id}", status_code=303)

    @router.get("/admin/prompts", response_class=HTMLResponse)
    def prompts_page(request: Request, db: Session = Depends(get_db), message: str = ""):
        admin_user = request.session.get("admin_user")
        if not admin_user:
            return RedirectResponse(url="/login", status_code=303)

        rows = prompt_loader.get_all_prompts(db)

        prompts = [
            {
                "version": p.version,
                "evaluation_prompt": p.evaluation_prompt,
                "clarification_rule": p.clarification_rule or "",
                "is_active": p.is_active,
                "created_at": p.created_at.strftime("%d-%m-%Y %H:%M:%S") if p.created_at else "-",
            }
            for p in rows
        ]

        return templates.TemplateResponse(
            request=request,
            name="prompts.html",
            context={
                "admin_user": admin_user,
                "prompts": prompts,
                "message": message,
            },
        )

    @router.post("/admin/prompts")
    def create_prompt(
        request: Request,
        version: str = Form(...),
        evaluation_prompt: str = Form(...),
        clarification_rule: str = Form(""),
        activate_now: str = Form("no"),
        db: Session = Depends(get_db),
    ):
        admin_user = request.session.get("admin_user")
        if not admin_user:
            return RedirectResponse(url="/login", status_code=303)

        activate = activate_now == "yes"

        try:
            prompt_loader.create_prompt(
                db=db,
                version=version.strip(),
                evaluation_prompt=evaluation_prompt.strip(),
                clarification_rule=clarification_rule.strip(),
                activate=activate,
            )
        except ValueError:
            return RedirectResponse(
                url="/admin/prompts?message=Prompt+version+already+exists",
                status_code=303,
            )

        return RedirectResponse(
            url=f"/admin/prompts?message=Prompt+version+{version.strip()}+created+successfully",
            status_code=303,
        )

    @router.post("/admin/prompts/{version}/activate")
    def activate_prompt(version: str, request: Request, db: Session = Depends(get_db)):
        admin_user = request.session.get("admin_user")
        if not admin_user:
            return RedirectResponse(url="/login", status_code=303)

        try:
            prompt_loader.activate_prompt(db, version)
        except ValueError:
            return RedirectResponse(
                url="/admin/prompts?message=Prompt+version+not+found",
                status_code=303,
            )

        return RedirectResponse(
            url=f"/admin/prompts?message=Prompt+version+{version}+activated+successfully",
            status_code=303,
        )

    @router.post("/admin/prompts/{version}/delete")
    def delete_prompt(version: str, request: Request, db: Session = Depends(get_db)):
        admin_user = request.session.get("admin_user")
        if not admin_user:
            return RedirectResponse(url="/login", status_code=303)

        prompt = (
            db.query(PromptVersion)
            .filter(PromptVersion.version == version)
            .first()
        )

        if not prompt:
            return RedirectResponse(
                url="/admin/prompts?message=Prompt+version+not+found",
                status_code=303,
            )

        if prompt.is_active:
            return RedirectResponse(
                url="/admin/prompts?message=Cannot+delete+the+active+prompt+version",
                status_code=303,
            )

        db.delete(prompt)
        db.commit()

        return RedirectResponse(
            url=f"/admin/prompts?message=Prompt+version+{version}+deleted+successfully",
            status_code=303
        )

    @router.get("/admin/feedback-summary", response_class=HTMLResponse)
    def feedback_summary(request: Request, db: Session = Depends(get_db)):
        admin_user = request.session.get("admin_user")
        if not admin_user:
            return RedirectResponse(url="/login", status_code=303)

        feedback_rows = db.query(Feedback).all()
        conversations = db.query(Conversation).all()

        conversation_map = {c.id: c for c in conversations}

        total_feedback = len(feedback_rows)

        overall_values = [f.overall_rating for f in feedback_rows if f.overall_rating is not None]
        fairness_values = [f.fairness_rating for f in feedback_rows if f.fairness_rating is not None]
        relevance_values = [f.relevance_rating for f in feedback_rows if f.relevance_rating is not None]

        def avg(values):
            return round(sum(values) / len(values), 2) if values else 0.0

        summary = {
            "total_feedback": total_feedback,
            "avg_overall": avg(overall_values),
            "avg_fairness": avg(fairness_values),
            "avg_relevance": avg(relevance_values),
        }

        skill_counts = defaultdict(int)
        skill_overall = defaultdict(list)
        prompt_counts = defaultdict(int)
        prompt_overall = defaultdict(list)
        flag_counter = Counter()

        for f in feedback_rows:
            conv = conversation_map.get(f.conversation_id)
            skill_name = conv.skill if conv and conv.skill else "Unknown"
            prompt_ver = conv.prompt_version if conv and conv.prompt_version else "Unknown"

            skill_counts[skill_name] += 1
            prompt_counts[prompt_ver] += 1

            if f.overall_rating is not None:
                skill_overall[skill_name].append(f.overall_rating)
                prompt_overall[prompt_ver].append(f.overall_rating)

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

        skill_summary = []
        for skill_name, count in skill_counts.items():
            skill_summary.append(
                {
                    "skill": skill_name,
                    "feedback_count": count,
                    "avg_overall": avg(skill_overall[skill_name]),
                }
            )
        skill_summary.sort(key=lambda x: x["skill"])

        prompt_summary = []
        for version, count in prompt_counts.items():
            prompt_summary.append(
                {
                    "prompt_version": version,
                    "feedback_count": count,
                    "avg_overall": avg(prompt_overall[version]),
                }
            )
        prompt_summary.sort(key=lambda x: x["prompt_version"])

        top_flags = [{"flag": flag, "count": count} for flag, count in flag_counter.most_common(10)]

        return templates.TemplateResponse(
            request=request,
            name="feedback_summary.html",
            context={
                "admin_user": admin_user,
                "summary": summary,
                "skill_summary": skill_summary,
                "prompt_summary": prompt_summary,
                "top_flags": top_flags,
            },
        )

    @router.get("/admin/prompt-suggestions", response_class=HTMLResponse)
    def prompt_suggestions_page(request: Request, db: Session = Depends(get_db)):
        admin_user = request.session.get("admin_user")
        if not admin_user:
            return RedirectResponse(url="/login", status_code=303)

        feedback_rows = db.query(Feedback).all()
        conversations = db.query(Conversation).all()

        feedback_summary = prompt_suggestion_service.build_feedback_summary(
            feedback_rows=feedback_rows,
            conversations=conversations,
        )

        suggestions_result = prompt_suggestion_service.generate_prompt_suggestions(feedback_summary)

        return templates.TemplateResponse(
            request=request,
            name="prompt_suggestions.html",
            context={
                "admin_user": admin_user,
                "feedback_summary": feedback_summary,
                "suggestions_result": suggestions_result,
            },
        )

    @router.get("/admin/compare", response_class=HTMLResponse)
    def compare_conversations_page(
        request: Request,
        db: Session = Depends(get_db),
        conversation_a: str = "",
        conversation_b: str = "",
        message: str = "",
    ):
        admin_user = request.session.get("admin_user")
        if not admin_user:
            return RedirectResponse(url="/login", status_code=303)

        def build_conversation_payload(conversation_id: str):
            if not conversation_id:
                return None

            conv = (
                db.query(Conversation)
                .filter(Conversation.id == conversation_id)
                .first()
            )
            if not conv:
                return None

            message_rows = (
                db.query(Message)
                .filter(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.asc())
                .all()
            )

            feedback_rows = (
                db.query(Feedback)
                .filter(Feedback.conversation_id == conversation_id)
                .order_by(Feedback.created_at.desc())
                .all()
            )

            feedback_entries = []
            for f in feedback_rows:
                try:
                    parsed_flags = json.loads(f.flags) if f.flags else []
                except Exception:
                    parsed_flags = [f.flags] if f.flags else []

                feedback_entries.append(
                    {
                        "evaluator": f.evaluator or "-",
                        "overall_rating": f.overall_rating,
                        "fairness_rating": f.fairness_rating,
                        "relevance_rating": f.relevance_rating,
                        "flags": parsed_flags,
                        "comments": f.comments or "",
                        "created_at": f.created_at.strftime("%d-%m-%Y %H:%M:%S") if f.created_at else "-",
                    }
                )

            return {
                "id": conv.id,
                "skill": conv.skill or "-",
                "status": conv.status,
                "stage": conv.stage,
                "prompt_version": conv.prompt_version or "-",
                "created_at": conv.created_at.strftime("%d-%m-%Y %H:%M:%S") if conv.created_at else "-",
                "completed_at": conv.completed_at.strftime("%d-%m-%Y %H:%M:%S") if conv.completed_at else "-",
                "messages": [
                    {
                        "role": m.role,
                        "content": m.content,
                        "question_index": (m.question_index + 1) if m.question_index is not None else None,
                        "created_at": m.created_at.strftime("%d-%m-%Y %H:%M:%S") if m.created_at else "-",
                    }
                    for m in message_rows
                ],
                "feedback_entries": feedback_entries,
            }

        conversation_a_data = build_conversation_payload(conversation_a.strip())
        conversation_b_data = build_conversation_payload(conversation_b.strip())

        if conversation_a.strip() and not conversation_a_data:
            logger.warning("Conversation A not found in compare: %s", conversation_a.strip())
            message = f"Conversation A not found: {conversation_a.strip()}"

        if conversation_b.strip() and not conversation_b_data:
            logger.warning("Conversation B not found in compare: %s", conversation_b.strip())
            if message:
                message += f" | Conversation B not found: {conversation_b.strip()}"
            else:
                message = f"Conversation B not found: {conversation_b.strip()}"

        recent_conversations = (
            db.query(Conversation)
            .order_by(Conversation.created_at.desc())
            .limit(20)
            .all()
        )

        recent_options = [
            {
                "id": c.id,
                "label": f"{c.id} | {c.skill or '-'} | {c.prompt_version or '-'} | {c.status}"
            }
            for c in recent_conversations
        ]

        recent_comparisons = (
            db.query(ComparisonFeedback)
            .order_by(ComparisonFeedback.created_at.desc())
            .limit(20)
            .all()
        )

        comparison_history = [
            {
                "conversation_a_id": c.conversation_a_id,
                "conversation_b_id": c.conversation_b_id,
                "prompt_version_a": c.prompt_version_a or "-",
                "prompt_version_b": c.prompt_version_b or "-",
                "evaluator": c.evaluator or "-",
                "preference": c.preference,
                "notes": c.notes or "",
                "created_at": c.created_at.strftime("%d-%m-%Y %H:%M:%S") if c.created_at else "-",
            }
            for c in recent_comparisons
        ]

        version_pair_stats = defaultdict(lambda: {"wins": {}, "ties": 0, "total": 0})

        all_comparisons = db.query(ComparisonFeedback).all()
        for row in all_comparisons:
            version_a = row.prompt_version_a or "-"
            version_b = row.prompt_version_b or "-"

            sorted_pair = sorted([version_a, version_b])
            pair_key = f"{sorted_pair[0]} vs {sorted_pair[1]}"

            version_pair_stats[pair_key]["total"] += 1

            if row.preference == "Tie":
                version_pair_stats[pair_key]["ties"] += 1
            else:
                winner = version_a if row.preference == "A" else version_b
                if winner not in version_pair_stats[pair_key]["wins"]:
                    version_pair_stats[pair_key]["wins"][winner] = 0
                version_pair_stats[pair_key]["wins"][winner] += 1

        version_comparison_summary = []
        for pair, stats in version_pair_stats.items():
            wins = stats["wins"]
            win_summary = ", ".join([f"{k}: {v}" for k, v in wins.items()]) if wins else "-"

            version_comparison_summary.append(
                {
                    "pair": pair,
                    "win_summary": win_summary,
                    "ties": stats["ties"],
                    "total": stats["total"],
                }
            )

        version_comparison_summary.sort(key=lambda x: x["pair"])

        return templates.TemplateResponse(
            request=request,
            name="compare_conversations.html",
            context={
                "admin_user": admin_user,
                "conversation_a_input": conversation_a,
                "conversation_b_input": conversation_b,
                "conversation_a_data": conversation_a_data,
                "conversation_b_data": conversation_b_data,
                "recent_options": recent_options,
                "comparison_history": comparison_history,
                "version_comparison_summary": version_comparison_summary,
                "message": message,
            },
        )

    @router.post("/admin/compare/preference")
    def submit_comparison_preference(
        request: Request,
        conversation_a_id: str = Form(...),
        conversation_b_id: str = Form(...),
        preference: str = Form(...),
        notes: str = Form(""),
        db: Session = Depends(get_db),
    ):
        admin_user = request.session.get("admin_user")
        if not admin_user:
            return RedirectResponse(url="/login", status_code=303)

        if preference not in {"A", "B", "Tie"}:
            return RedirectResponse(
                url=f"/admin/compare?conversation_a={conversation_a_id}&conversation_b={conversation_b_id}&message=Invalid+preference",
                status_code=303,
            )

        conv_a = (
            db.query(Conversation)
            .filter(Conversation.id == conversation_a_id.strip())
            .first()
        )
        conv_b = (
            db.query(Conversation)
            .filter(Conversation.id == conversation_b_id.strip())
            .first()
        )

        if not conv_a or not conv_b:
            logger.warning(
                "Comparison save failed. conversation_a_id=%s conversation_b_id=%s",
                conversation_a_id,
                conversation_b_id,
            )
            return RedirectResponse(
                url=f"/admin/compare?conversation_a={conversation_a_id}&conversation_b={conversation_b_id}&message=One+or+both+conversations+not+found",
                status_code=303,
            )

        comparison = ComparisonFeedback(
            conversation_a_id=conv_a.id,
            conversation_b_id=conv_b.id,
            prompt_version_a=conv_a.prompt_version or "-",
            prompt_version_b=conv_b.prompt_version or "-",
            evaluator=admin_user,
            preference=preference,
            notes=notes.strip(),
        )

        db.add(comparison)
        db.commit()

        return RedirectResponse(
            url=f"/admin/compare?conversation_a={conversation_a_id}&conversation_b={conversation_b_id}&message=Comparison+preference+saved+successfully",
            status_code=303,
        )

    return router