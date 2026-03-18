from typing import Any, AsyncGenerator, Dict, List, Optional
from litellm import acompletion  # type: ignore[import-not-found]
from pydantic import BaseModel


class LLMMessage(BaseModel):
    role: str
    content: str


class LiteLLMClient:
    """
    An async generator LiteLLM adapter matching the OpenAI SDK format.
    Supports streaming and standard completion.
    """

    def __init__(self, model_name: str = "gpt-4o", timeout: float = 300.0):
        self.model_name = model_name
        self.timeout = timeout

    async def astream_chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """
        Stream the response from the LLM.
        """
        formatted_messages = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})

        formatted_messages.extend(messages)

        response = await acompletion(
            model=self.model_name,
            messages=formatted_messages,
            stream=True,
            temperature=temperature,
            timeout=self.timeout,
            **kwargs,
        )

        async for chunk in response:
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content

    async def achat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Get the full response from the LLM without streaming.
        Returns a dict with keys: content, cost_usd, total_tokens
        """
        from litellm import completion_cost

        formatted_messages = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})

        formatted_messages.extend(messages)

        response = await acompletion(
            model=self.model_name,
            messages=formatted_messages,
            stream=False,
            temperature=temperature,
            timeout=self.timeout,
            **kwargs,
        )

        content = ""
        if response.choices and len(response.choices) > 0:
            content = response.choices[0].message.content or ""

        # Calculate cost using litellm
        cost_usd = completion_cost(
            completion_response=response,
            model=self.model_name,
        )

        # Extract token breakdown from usage
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        if hasattr(response, "usage") and response.usage:
            prompt_tokens = response.usage.prompt_tokens or 0
            completion_tokens = response.usage.completion_tokens or 0
            total_tokens = response.usage.total_tokens or 0

        return {
            "content": content,
            "cost_usd": cost_usd,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }
