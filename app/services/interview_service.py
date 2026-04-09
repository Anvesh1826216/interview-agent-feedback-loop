import json
import logging
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.agent.enums import InterviewStage
from app.agent.exceptions import ConversationNotFoundError, InvalidStateError
from app.agent.state import InterviewState
from app.db.models import Conversation, Message

logger = logging.getLogger(__name__)


class InterviewService:
    def __init__(self, fsm):
        self.fsm = fsm

    def start_interview(self, db: Session):
        conversation_id = str(uuid.uuid4())
        state = InterviewState(
            conversation_id=conversation_id,
            stage=InterviewStage.START,
        )

        agent_messages = []

        logger.info("Starting new interview: conversation_id=%s", conversation_id)

        while state.stage != InterviewStage.WAIT_FOR_ANSWER:
            state, output = self.fsm.step(state, db=db)
            if output and output.strip():
                agent_messages.append(output)

        conversation = Conversation(
            id=conversation_id,
            skill=state.skill,
            status=state.status,
            stage=state.stage.value,
            prompt_version=state.prompt_version,
            state_json=json.dumps(state.to_dict()),
        )
        db.add(conversation)

        question_index = state.question_index
        for msg in agent_messages:
            db.add(
                Message(
                    conversation_id=conversation_id,
                    role="agent",
                    content=msg,
                    question_index=question_index if msg == state.current_question else None,
                )
            )

        db.commit()
        db.refresh(conversation)

        logger.info(
            "Interview started successfully: conversation_id=%s | skill=%s | prompt_version=%s",
            conversation.id,
            conversation.skill,
            conversation.prompt_version,
        )

        return {
            "conversation_id": conversation.id,
            "skill": conversation.skill,
            "stage": conversation.stage,
            "message": agent_messages[-1] if agent_messages else "",
            "prompt_version": conversation.prompt_version,
        }

    def respond(self, db: Session, conversation_id: str, answer: str):
        conversation = (
            db.query(Conversation)
            .filter(Conversation.id == conversation_id)
            .first()
        )

        if not conversation:
            raise ConversationNotFoundError("Conversation not found")

        try:
            state_data = json.loads(conversation.state_json)
            state = InterviewState.from_dict(state_data)
        except Exception as e:
            logger.exception("Failed to parse conversation state for %s: %s", conversation_id, e)
            raise InvalidStateError("Conversation state is corrupted or unreadable.")

        if state.stage != InterviewStage.WAIT_FOR_ANSWER:
            raise InvalidStateError(
                f"Conversation is not ready for user input. Current stage: {state.stage.value}"
            )

        logger.info(
            "Received candidate response: conversation_id=%s | question_index=%s",
            conversation_id,
            state.question_index,
        )

        db.add(
            Message(
                conversation_id=conversation_id,
                role="candidate",
                content=answer,
                question_index=state.question_index,
            )
        )

        visible_agent_messages = []

        # First step consumes user input
        state, output = self.fsm.step(state, db=db, user_input=answer)
        if output and output.strip():
            visible_agent_messages.append(output)
            db.add(
                Message(
                    conversation_id=conversation_id,
                    role="agent",
                    content=output,
                    question_index=state.question_index,
                )
            )

        # Continue until next user turn or interview end
        while state.stage not in [InterviewStage.WAIT_FOR_ANSWER, InterviewStage.END]:
            state, output = self.fsm.step(state, db=db)
            if output and output.strip():
                visible_agent_messages.append(output)
                db.add(
                    Message(
                        conversation_id=conversation_id,
                        role="agent",
                        content=output,
                        question_index=state.question_index if state.question_index < 3 else None,
                    )
                )

        conversation.skill = state.skill
        conversation.status = state.status
        conversation.stage = state.stage.value
        conversation.prompt_version = state.prompt_version
        conversation.state_json = json.dumps(state.to_dict())

        if state.stage == InterviewStage.END:
            conversation.completed_at = datetime.now()
            logger.info(
                "Interview completed: conversation_id=%s | skill=%s | prompt_version=%s",
                conversation_id,
                conversation.skill,
                conversation.prompt_version,
            )

        db.commit()
        db.refresh(conversation)

        final_message = visible_agent_messages[-1] if visible_agent_messages else ""

        return {
            "conversation_id": conversation.id,
            "stage": conversation.stage,
            "message": final_message,
            "completed": conversation.stage == InterviewStage.END,
        }

    def get_conversation(self, db: Session, conversation_id: str):
        conversation = (
            db.query(Conversation)
            .filter(Conversation.id == conversation_id)
            .first()
        )

        if not conversation:
            raise ConversationNotFoundError("Conversation not found")

        return conversation