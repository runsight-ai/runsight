import json
from dataclasses import dataclass
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


@dataclass(frozen=True)
class FallbackRoute:
    source_provider_id: str
    target_provider_id: str
    target_model_name: str


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
        model_name: str,
        api_keys: Optional[Dict[str, str]] = None,
        fallback_routes: Optional[Dict[str, FallbackRoute]] = None,
    ):
        self.model_name = model_name
        self.api_keys = api_keys
        self.fallback_routes = fallback_routes or {}
        # Resolve the default key for the runner's own model when canonical provider keys are available.
        default_key = self._resolve_key_for_model(model_name) if api_keys else None
        self.llm_client = LiteLLMClient(model_name=model_name, api_key=default_key)
        self._clients: Dict[str, LiteLLMClient] = {}

    def _resolve_runtime_model_name(self, soul: Soul) -> str:
        has_provider = isinstance(soul.provider, str) and bool(soul.provider.strip())
        has_model_name = isinstance(soul.model_name, str) and bool(soul.model_name.strip())

        if not has_provider and not has_model_name:
            raise ValueError(f"Soul '{soul.id}' must define an explicit provider and model_name")
        if has_model_name and not has_provider:
            raise ValueError(f"Soul '{soul.id}' must define an explicit provider")
        if has_provider and not has_model_name:
            raise ValueError(f"Soul '{soul.id}' must define an explicit model_name")
        if has_model_name:
            return soul.model_name  # type: ignore[return-value]
        raise ValueError(f"Soul '{soul.id}' must define an explicit provider and model_name")

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
        explicit_model_name = self._resolve_runtime_model_name(soul)

        # When api_keys dict is provided, always resolve per-model
        if self.api_keys is not None:
            cache_key = explicit_model_name
            if cache_key not in self._clients:
                key = self._resolve_key_for_model(explicit_model_name)
                self._clients[cache_key] = LiteLLMClient(
                    model_name=explicit_model_name, api_key=key
                )
            return self._clients[cache_key]

        if explicit_model_name == self.model_name:
            return self.llm_client
        if explicit_model_name not in self._clients:
            key = (
                self._resolve_key_for_model(explicit_model_name)
                if self.api_keys is not None
                else None
            )
            self._clients[explicit_model_name] = LiteLLMClient(
                model_name=explicit_model_name, api_key=key
            )
        return self._clients[explicit_model_name]

    @staticmethod
    def _is_retryable_provider_error(exc: Exception) -> bool:
        if isinstance(exc, (TimeoutError, ConnectionError)):
            return True

        name = type(exc).__name__.lower()
        module = type(exc).__module__.lower()
        message = str(exc).lower()
        non_retryable_signals = (
            "authentication",
            "autherror",
            "unauthorized",
            "forbidden",
            "permission",
            "invalid api key",
            "invalid_api_key",
            "credentials",
            "configuration",
            "configerror",
        )
        haystacks = (name, module, message)
        if any(signal in haystack for haystack in haystacks for signal in non_retryable_signals):
            return False

        signals = (
            "ratelimit",
            "timeout",
            "apierror",
            "apiconnection",
            "serviceunavailable",
            "internalservererror",
            "badgateway",
            "gatewaytimeout",
            "temporarily unavailable",
            "overloaded",
        )
        return any(signal in haystack for haystack in haystacks for signal in signals)

    def _fallback_soul(self, soul: Soul) -> Soul | None:
        if not soul.provider:
            return None
        route = self.fallback_routes.get(soul.provider)
        if route is None:
            return None
        return soul.model_copy(
            update={
                "model_name": route.target_model_name,
                "provider": route.target_provider_id,
            }
        )

    @staticmethod
    def _outstanding_required_tool_calls(soul: Soul, tool_calls_made: List[str]) -> List[str]:
        required_tool_calls = soul.required_tool_calls or []
        if not required_tool_calls:
            return []

        remaining: List[str] = []
        for tool_name in required_tool_calls:
            if tool_name not in tool_calls_made and tool_name not in remaining:
                remaining.append(tool_name)
        return remaining

    async def _achat_with_failover(
        self,
        soul: Soul,
        *,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str],
        tools: Optional[List[dict]] = None,
        tool_choice: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        allow_failover: bool = True,
    ) -> tuple[Dict[str, Any], Soul, bool]:
        active_soul = soul
        client = self._get_client(active_soul)
        request_kwargs: Dict[str, Any] = {}
        if temperature is not None:
            request_kwargs["temperature"] = temperature
        if max_tokens is not None:
            request_kwargs["max_tokens"] = max_tokens
        try:
            response = await client.achat(
                messages=messages,
                system_prompt=system_prompt,
                tools=tools,
                tool_choice=tool_choice,
                **request_kwargs,
            )
            return response, active_soul, allow_failover
        except Exception as exc:
            fallback_soul = self._fallback_soul(active_soul) if allow_failover else None
            if fallback_soul is None or not self._is_retryable_provider_error(exc):
                raise
            fallback_client = self._get_client(fallback_soul)
            response = await fallback_client.achat(
                messages=messages,
                system_prompt=system_prompt,
                tools=tools,
                tool_choice=tool_choice,
                **request_kwargs,
            )
            return response, fallback_soul, False

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
        active_soul = soul
        allow_failover = True

        # Single-shot path: no tools
        if not active_soul.resolved_tools:
            response, active_soul, allow_failover = await self._achat_with_failover(
                active_soul,
                messages=all_messages,
                system_prompt=active_soul.system_prompt,
                temperature=active_soul.temperature,
                max_tokens=active_soul.max_tokens,
                allow_failover=allow_failover,
            )
            return ExecutionResult(
                task_id=task.id,
                soul_id=active_soul.id,
                output=response["content"],
                cost_usd=response["cost_usd"],
                total_tokens=response["total_tokens"],
                tool_iterations=0,
                tool_calls_made=[],
            )

        # Agentic tool loop
        tool_schemas = [t.to_openai_schema() for t in active_soul.resolved_tools]
        tool_map = {t.name: t for t in active_soul.resolved_tools}
        for tool in active_soul.resolved_tools:
            source = getattr(tool, "source", None)
            if source:
                tool_map[str(source)] = tool
        max_iters = active_soul.max_tool_iterations
        iteration = 0
        accumulated_cost = 0.0
        accumulated_tokens = 0
        tool_calls_made: List[str] = []
        response: Dict[str, Any] = {}

        while iteration < max_iters:
            outstanding_required_tool_calls = self._outstanding_required_tool_calls(
                active_soul, tool_calls_made
            )
            is_last = iteration == max_iters - 1
            requires_more_tools = bool(outstanding_required_tool_calls)
            tools_for_llm = tool_schemas if requires_more_tools or not is_last else []
            tool_choice = "required" if requires_more_tools else None

            response, active_soul, allow_failover = await self._achat_with_failover(
                active_soul,
                messages=all_messages,
                system_prompt=active_soul.system_prompt,
                tools=tools_for_llm,
                tool_choice=tool_choice,
                temperature=active_soul.temperature,
                max_tokens=active_soul.max_tokens,
                allow_failover=allow_failover,
            )
            accumulated_cost += response["cost_usd"]
            accumulated_tokens += response["total_tokens"]

            if not response.get("tool_calls"):
                if outstanding_required_tool_calls:
                    missing = ", ".join(outstanding_required_tool_calls)
                    raise ValueError(
                        f"Soul '{active_soul.id}' stopped before required tool calls completed: {missing}"
                    )
                # LLM responded with text -- done
                return ExecutionResult(
                    task_id=task.id,
                    soul_id=active_soul.id,
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

        outstanding_required_tool_calls = self._outstanding_required_tool_calls(
            active_soul, tool_calls_made
        )
        if outstanding_required_tool_calls:
            missing = ", ".join(outstanding_required_tool_calls)
            raise ValueError(
                f"Soul '{active_soul.id}' exhausted max_tool_iterations before required tool calls completed: {missing}"
            )

        # Max iterations exhausted -- force a final text response with no tools
        response, active_soul, _ = await self._achat_with_failover(
            active_soul,
            messages=all_messages,
            system_prompt=active_soul.system_prompt,
            tools=[],
            temperature=active_soul.temperature,
            max_tokens=active_soul.max_tokens,
            allow_failover=allow_failover,
        )
        accumulated_cost += response["cost_usd"]
        accumulated_tokens += response["total_tokens"]

        return ExecutionResult(
            task_id=task.id,
            soul_id=active_soul.id,
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
