from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.interview_service import InterviewService


templates = Jinja2Templates(directory="app/ui/templates")


def create_ui_routes(interview_service: InterviewService) -> APIRouter:
    router = APIRouter()

    @router.get("/", response_class=HTMLResponse)
    def home(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="home.html",
            context={},
        )

    @router.post("/ui/interviews/start")
    def start_interview(db: Session = Depends(get_db)):
        result = interview_service.start_interview(db)
        conversation_id = result["conversation_id"]
        return RedirectResponse(url=f"/ui/interviews/{conversation_id}", status_code=303)

    @router.get("/ui/interviews/{conversation_id}", response_class=HTMLResponse)
    def interview_page(
        conversation_id: str,
        request: Request,
        db: Session = Depends(get_db),
    ):
        try:
            conversation = interview_service.get_conversation(db, conversation_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

        messages = sorted(conversation.messages, key=lambda m: m.created_at)

        current_question_number = 1
        indexed_messages = [m for m in messages if m.question_index is not None]
        if indexed_messages:
            current_question_number = min(indexed_messages[-1].question_index + 1, 3)

        return templates.TemplateResponse(
            request=request,
            name="interview.html",
            context={
                "conversation": conversation,
                "messages": messages,
                "completed": conversation.stage == "end",
                "current_question_number": current_question_number,
                "total_questions": 3,
            },
        )

    @router.post("/ui/interviews/{conversation_id}/answer")
    def submit_answer(
        conversation_id: str,
        answer: str = Form(...),
        db: Session = Depends(get_db),
    ):
        try:
            interview_service.respond(db, conversation_id, answer)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        return RedirectResponse(url=f"/ui/interviews/{conversation_id}", status_code=303)

    return router