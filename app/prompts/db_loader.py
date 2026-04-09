from sqlalchemy.orm import Session

from app.db.models import PromptVersion
from app.agent.exceptions import PromptNotFoundError


class DBPromptLoader:
    def get_active_prompts(self, db):
        prompt = (
            db.query(PromptVersion)
            .filter(PromptVersion.is_active == True)
            .first()
        )

        if not prompt:
            raise PromptNotFoundError("No active prompt version found. Please create and activate a prompt version.")

        return {
            "version": prompt.version,
            "evaluation_prompt": prompt.evaluation_prompt,
            "clarification_rule": prompt.clarification_rule or "",
        }

    def get_all_prompts(self, db: Session):
        return (
            db.query(PromptVersion)
            .order_by(PromptVersion.created_at.desc())
            .all()
        )

    def create_prompt(
        self,
        db: Session,
        version: str,
        evaluation_prompt: str,
        clarification_rule: str = "",
        activate: bool = False,
    ):
        existing = (
            db.query(PromptVersion)
            .filter(PromptVersion.version == version)
            .first()
        )
        if existing:
            raise ValueError(f"Prompt version '{version}' already exists.")

        if activate:
            db.query(PromptVersion).update({"is_active": False})

        prompt = PromptVersion(
            version=version,
            evaluation_prompt=evaluation_prompt,
            clarification_rule=clarification_rule,
            is_active=activate,
        )
        db.add(prompt)
        db.commit()
        db.refresh(prompt)
        return prompt

    def activate_prompt(self, db: Session, version: str):
        prompt = (
            db.query(PromptVersion)
            .filter(PromptVersion.version == version)
            .first()
        )
        if not prompt:
            raise ValueError(f"Prompt version '{version}' not found.")

        db.query(PromptVersion).update({"is_active": False})
        prompt.is_active = True
        db.commit()
        db.refresh(prompt)
        return prompt