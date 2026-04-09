from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agent.schemas import (
    ConversationResponse,
    MessageResponse,
    RespondRequest,
    RespondResponse,
    StartInterviewResponse,
)
from app.db.database import get_db
from app.services.interview_service import InterviewService


router = APIRouter()


def build_conversation_response(conversation) -> ConversationResponse:
    return ConversationResponse(
        conversation_id=conversation.id,
        skill=conversation.skill,
        status=conversation.status,
        stage=conversation.stage,
        prompt_version=conversation.prompt_version,
        created_at=conversation.created_at.isoformat(),
        completed_at=conversation.completed_at.isoformat() if conversation.completed_at else None,
        messages=[
            MessageResponse(
                role=m.role,
                content=m.content,
                question_index=m.question_index,
                created_at=m.created_at.isoformat(),
            )
            for m in conversation.messages
        ],
    )


def create_interview_routes(interview_service: InterviewService) -> APIRouter:
    api_router = APIRouter()

    @api_router.post("/interviews/start", response_model=StartInterviewResponse)
    def start_interview(db: Session = Depends(get_db)):
        try:
            result = interview_service.start_interview(db)
            return StartInterviewResponse(**result)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @api_router.post("/interviews/{conversation_id}/respond", response_model=RespondResponse)
    def respond(conversation_id: str, payload: RespondRequest, db: Session = Depends(get_db)):
        try:
            result = interview_service.respond(db, conversation_id, payload.answer)
            return RespondResponse(**result)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @api_router.get("/interviews/{conversation_id}", response_model=ConversationResponse)
    def get_conversation(conversation_id: str, db: Session = Depends(get_db)):
        try:
            conversation = interview_service.get_conversation(db, conversation_id)
            return build_conversation_response(conversation)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @api_router.get("/health")
    def health():
        return {"status": "ok"}

    return api_router


