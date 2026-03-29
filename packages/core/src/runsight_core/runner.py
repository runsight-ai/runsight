import json
from typing import Any, AsyncGenerator, Dict, List, Optional

from pydantic import BaseModel, Field

from runsight_core.llm.client import LiteLLMClient
from runsight_core.primitives import Soul, Task


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
    tool_iterations: int = 0
    tool_calls_made: List[str] = Field(default_factory=list)


def _detect_provider(model_name: str) -> str:
    """Use litellm to detect the provider for a model name.

    Returns the provider string (e.g. 'openai', 'anthropic').
    Raises ValueError if the model cannot be mapped to a provider.
    """
    import litellm

    try:
        _model, provider, *_ = litellm.get_llm_provider(model_name)
        return provider
    except Exception:
        raise ValueError(
            f"Cannot determine provider for model '{model_name}'. "
            f"Ensure the model name is valid (see https://docs.litellm.ai/docs/providers)."
        )


class RunsightTeamRunner:
    """
    Core executor that runs a Task using a specific Soul via the LLM client.
    """

    def __init__(
        self,
        model_name: str = "gpt-4o",
        api_key: str | None = None,
        api_keys: Optional[Dict[str, str]] = None,
    ):
        self.model_name = model_name
        self.api_key = api_key
        self.api_keys = api_keys
        # Resolve the default key for the runner's own model
        default_key = self._resolve_key_for_model(model_name) if api_keys else api_key
        self.llm_client = LiteLLMClient(model_name=model_name, api_key=default_key)
        self._clients: Dict[str, LiteLLMClient] = {}

    def _resolve_key_for_model(self, model_name: str) -> str:
        """Look up the API key for a model from the api_keys dict."""
        provider = _detect_provider(model_name)
        if provider not in self.api_keys:
            raise ValueError(
                f"No API key configured for provider '{provider}' "
                f"(required by model '{model_name}'). "
                f"Available providers: {sorted(self.api_keys.keys())}"
            )
        return self.api_keys[provider]

    def _get_client(self, soul: Soul) -> LiteLLMClient:
        """Return LLM client for soul, using soul's model override if set.

        Thread-safety invariant:
            The check-then-set on ``self._clients`` has no lock, but is safe
            because there is no ``await`` between the ``if cache_key not in``
            check and the ``self._clients[cache_key] = ...`` assignment.
            Under Python's GIL + cooperative async scheduling, only an
            ``await`` can yield control to another coroutine.

            If ``_resolve_key_for_model`` (or any helper called here) ever
            becomes async, this turns into a race condition under
            ``asyncio.gather`` (e.g. FanOutBlock launching parallel souls).
            In that case, replace with an ``asyncio.Lock`` guarding the
            check-then-set block.
        """
        # When api_keys dict is provided, always resolve per-model
        if self.api_keys is not None:
            effective_model = soul.model_name or self.model_name
            cache_key = effective_model
            if cache_key not in self._clients:
                key = self._resolve_key_for_model(effective_model)
                self._clients[cache_key] = LiteLLMClient(model_name=effective_model, api_key=key)
            return self._clients[cache_key]

        # Legacy single api_key path
        override = soul.model_name
        if override is None or override == self.model_name:
            return self.llm_client
        if override not in self._clients:
            self._clients[override] = LiteLLMClient(model_name=override, api_key=self.api_key)
        return self._clients[override]

    async def execute_task(
        self, task: Task, soul: Soul, messages: list[dict] | None = None
    ) -> ExecutionResult:
        """
        Executes a task synchronously (waits for full completion).

        When the soul has resolved_tools, enters an agentic tool-use loop:
        sends tool schemas to the LLM, executes tool calls, feeds results back,
        and repeats until the LLM responds with text or max iterations is reached.
        """
        all_messages = (messages or []) + [{"role": "user", "content": self._build_prompt(task)}]
        client = self._get_client(soul)

        # Single-shot path: no tools
        if not soul.resolved_tools:
            response = await client.achat(messages=all_messages, system_prompt=soul.system_prompt)
            return ExecutionResult(
                task_id=task.id,
                soul_id=soul.id,
                output=response["content"],
                cost_usd=response["cost_usd"],
                total_tokens=response["total_tokens"],
                tool_iterations=0,
                tool_calls_made=[],
            )

        # Agentic tool loop
        tool_schemas = [t.to_openai_schema() for t in soul.resolved_tools]
        tool_map = {t.name: t for t in soul.resolved_tools}
        max_iters = soul.max_tool_iterations
        iteration = 0
        accumulated_cost = 0.0
        accumulated_tokens = 0
        tool_calls_made: List[str] = []
        response: Dict[str, Any] = {}

        while iteration < max_iters:
            is_last = iteration == max_iters - 1
            tools_for_llm = [] if is_last else tool_schemas

            response = await client.achat(
                messages=all_messages,
                system_prompt=soul.system_prompt,
                tools=tools_for_llm,
            )
            accumulated_cost += response["cost_usd"]
            accumulated_tokens += response["total_tokens"]

            if not response.get("tool_calls"):
                # LLM responded with text -- done
                return ExecutionResult(
                    task_id=task.id,
                    soul_id=soul.id,
                    output=response["content"],
                    cost_usd=accumulated_cost,
                    total_tokens=accumulated_tokens,
                    tool_iterations=iteration,
                    tool_calls_made=tool_calls_made,
                )

            # Append assistant message with tool_calls to conversation
            all_messages.append(response["raw_message"])

            # Execute each tool call
            for tc in response["tool_calls"]:
                tool_name = tc["function"]["name"]
                tool_calls_made.append(tool_name)

                tool = tool_map.get(tool_name)
                if tool is None:
                    result_str = f"Error: unknown tool '{tool_name}'"
                else:
                    try:
                        args = json.loads(tc["function"]["arguments"])
                        result_str = await tool.execute(args)
                    except Exception as e:
                        result_str = f"Error: {e}"

                all_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result_str,
                    }
                )

            iteration += 1

        # Max iterations exhausted -- force a final text response with no tools
        response = await client.achat(
            messages=all_messages,
            system_prompt=soul.system_prompt,
            tools=[],
        )
        accumulated_cost += response["cost_usd"]
        accumulated_tokens += response["total_tokens"]

        return ExecutionResult(
            task_id=task.id,
            soul_id=soul.id,
            output=response.get("content", ""),
            cost_usd=accumulated_cost,
            total_tokens=accumulated_tokens,
            tool_iterations=iteration,
            tool_calls_made=tool_calls_made,
        )

    async def stream_task(
        self, task: Task, soul: Soul, messages: list[dict] | None = None
    ) -> AsyncGenerator[str, None]:
        """
        Executes a task and streams the response tokens back.
        """
        all_messages = (messages or []) + [{"role": "user", "content": self._build_prompt(task)}]

        client = self._get_client(soul)
        async for chunk in client.astream_chat(
            messages=all_messages, system_prompt=soul.system_prompt
        ):
            yield chunk

    def _build_prompt(self, task: Task) -> str:
        """
        Constructs the final prompt string from the task definition.
        """
        prompt = task.instruction
        if task.context:
            prompt += f"\n\nContext:\n{task.context}"
        return prompt
