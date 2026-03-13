from sqlmodel import SQLModel, Field
from typing import Optional, List
import json
import time


class Provider(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    type: str = "custom"  # openai | anthropic | google | azure_openai | aws_bedrock | mistral | cohere | groq | together | ollama | custom
    api_key_encrypted: Optional[str] = None
    base_url: Optional[str] = None
    is_active: bool = Field(default=True)
    status: str = Field(default="unknown")  # unknown | active | connected | error | offline
    models_json: Optional[str] = Field(default=None)
    last_status_check: Optional[float] = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

    @property
    def models(self) -> List[str]:
        if not self.models_json:
            return []
        try:
            return json.loads(self.models_json)
        except (json.JSONDecodeError, TypeError):
            return []

    @models.setter
    def models(self, value: List[str]) -> None:
        self.models_json = json.dumps(value) if value else None
