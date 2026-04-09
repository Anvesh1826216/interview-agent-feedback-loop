import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.admin.routes import create_admin_routes
from app.agent.exceptions import (
    ConversationNotFoundError,
    InvalidStateError,
    LLMUnavailableError,
    MissingUserInputError,
    PromptNotFoundError,
)
from app.agent.fsm import InterviewFSM
from app.core.config import settings
from app.db.database import Base, SessionLocal, engine
from app.db.models import Conversation
from app.llm.llm_service import LLMService
from app.llm.mock_llm import MockLLMService
from app.prompts.db_loader import DBPromptLoader
from app.services.interview_service import InterviewService
from app.ui.routes import create_ui_routes

# -----------------------------------
# Logging
# -----------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# -----------------------------------
# App
# -----------------------------------
app = FastAPI(title="Interview Intelligence Platform")

# -----------------------------------
# Middleware
# -----------------------------------
app.add_middleware(
    SessionMiddleware,
    secret_key=getattr(settings, "SESSION_SECRET_KEY", "dev-secret-key"),
)

# -----------------------------------
# Static files
# -----------------------------------
app.mount("/static", StaticFiles(directory="app/ui/static"), name="static")

# -----------------------------------
# DB init
# -----------------------------------
Base.metadata.create_all(bind=engine)
logger.info("Database tables ensured.")

# -----------------------------------
# Services
# -----------------------------------
prompt_loader = DBPromptLoader()

if getattr(settings, "USE_MOCK_LLM", False):
    llm_service = MockLLMService()
    logger.info("Using Mock LLM service.")
else:
    llm_service = LLMService()
    logger.info("Using real LLM service.")

fsm = InterviewFSM(llm_service=llm_service, prompt_loader=prompt_loader)
interview_service = InterviewService(fsm=fsm)

# -----------------------------------
# Routers
# -----------------------------------
app.include_router(create_ui_routes(interview_service))
app.include_router(create_admin_routes())

# -----------------------------------
# Health check + basic metrics
# -----------------------------------
@app.get("/health")
def health_check():
    db: Session = SessionLocal()
    try:
        interviews_started = db.query(Conversation).count()
        interviews_completed = (
            db.query(Conversation)
            .filter(Conversation.status == "completed")
            .count()
        )

        if interviews_started > 0:
            interview_completion_rate = round(
                (interviews_completed / interviews_started) * 100, 2
            )
        else:
            interview_completion_rate = 0.0

        return {
            "status": "ok",
            "app": "Interview Intelligence Platform",
            "mock_llm": bool(getattr(settings, "USE_MOCK_LLM", False)),
            "interviews_started": interviews_started,
            "interviews_completed": interviews_completed,
            "interview_completion_rate": interview_completion_rate,
        }
    finally:
        db.close()

# -----------------------------------
# Exception handlers
# -----------------------------------
@app.exception_handler(MissingUserInputError)
async def missing_input_handler(request: Request, exc: MissingUserInputError):
    logger.warning("Missing user input: %s", exc)
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)},
    )


@app.exception_handler(ConversationNotFoundError)
async def conversation_not_found_handler(request: Request, exc: ConversationNotFoundError):
    logger.warning("Conversation not found: %s", exc)
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)},
    )


@app.exception_handler(PromptNotFoundError)
async def prompt_not_found_handler(request: Request, exc: PromptNotFoundError):
    logger.error("Prompt not found: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )


@app.exception_handler(InvalidStateError)
async def invalid_state_handler(request: Request, exc: InvalidStateError):
    logger.exception("Invalid FSM state: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "The interview reached an unexpected state. Please start a new interview."},
    )


@app.exception_handler(LLMUnavailableError)
async def llm_unavailable_handler(request: Request, exc: LLMUnavailableError):
    logger.exception("LLM unavailable: %s", exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "The interview model is temporarily unavailable. Please try again shortly."},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled application error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again."},
    )