import json
from pathlib import Path


class PromptLoader:
    def __init__(self, path: str = "app/prompts/prompts.json"):
        self.path = Path(path)

    def load_all(self) -> dict:
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_active_version(self) -> str:
        data = self.load_all()
        return data["active_version"]

    def get_active_prompts(self) -> dict:
        data = self.load_all()
        version = data["active_version"]
        return {
            "version": version,
            **data["versions"][version]
        }