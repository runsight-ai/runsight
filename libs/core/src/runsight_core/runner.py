from typing import Any, AsyncGenerator, Dict
from pydantic import BaseModel

from runsight_core.primitives import Soul, Task
from runsight_core.llm.client import LiteLLMClient


class ExecutionResult(BaseModel):
    """
    The result of a single task execution by an agent.
    """

    task_id: str
    soul_id: str
    output: str
    metadata: Dict[str, Any] = {}
    cost_usd: float = 0.0
    total_tokens: int = 0


class RunsightTeamRunner:
    """
    Core executor that runs a Task using a specific Soul via the LLM client.
    """

    def __init__(self, model_name: str = "gpt-4o", api_key: str | None = None):
        self.model_name = model_name
        self.api_key = api_key
        self.llm_client = LiteLLMClient(model_name=model_name, api_key=api_key)
        self._clients: Dict[str, LiteLLMClient] = {}

    def _get_client(self, soul: Soul) -> LiteLLMClient:
        """Return LLM client for soul, using soul's model override if set."""
        override = soul.model_name
        if override is None or override == self.model_name:
            return self.llm_client
        if override not in self._clients:
            self._clients[override] = LiteLLMClient(model_name=override, api_key=self.api_key)
        return self._clients[override]

    async def execute_task(self, task: Task, soul: Soul) -> ExecutionResult:
        """
        Executes a task synchronously (waits for full completion).
        """
        messages = [{"role": "user", "content": self._build_prompt(task)}]

        client = self._get_client(soul)
        response = await client.achat(messages=messages, system_prompt=soul.system_prompt)

        return ExecutionResult(
            task_id=task.id,
            soul_id=soul.id,
            output=response["content"],
            cost_usd=response["cost_usd"],
            total_tokens=response["total_tokens"],
        )

    async def stream_task(self, task: Task, soul: Soul) -> AsyncGenerator[str, None]:
        """
        Executes a task and streams the response tokens back.
        """
        messages = [{"role": "user", "content": self._build_prompt(task)}]

        client = self._get_client(soul)
        async for chunk in client.astream_chat(messages=messages, system_prompt=soul.system_prompt):
            yield chunk

    def _build_prompt(self, task: Task) -> str:
        """
        Constructs the final prompt string from the task definition.
        """
        prompt = task.instruction
        if task.context:
            prompt += f"\n\nContext:\n{task.context}"
        return prompt
