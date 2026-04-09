import os


class Settings:
    APP_NAME = "Interview Agent"
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./interview_agent.db")
    USE_MOCK_LLM = os.getenv("USE_MOCK_LLM", "true").lower() == "true"        # change to "false" after the OpenAPI Key in ".env"

    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin@12345")
    SESSION_SECRET = os.getenv("SESSION_SECRET", "supersecretkey123")


settings = Settings()