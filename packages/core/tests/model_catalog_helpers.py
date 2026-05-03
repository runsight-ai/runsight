"""Shared synthetic LiteLLM catalog data for model catalog tests."""

from __future__ import annotations

import sys
import types
from contextlib import contextmanager
from unittest.mock import patch

FAKE_MODEL_COST = {
    "gpt-4o": {
        "litellm_provider": "openai",
        "mode": "chat",
        "max_tokens": 16384,
        "max_input_tokens": 128000,
        "input_cost_per_token": 0.000005,
        "output_cost_per_token": 0.000015,
        "supports_vision": True,
        "supports_function_calling": True,
    },
    "gpt-3.5-turbo": {
        "litellm_provider": "openai",
        "mode": "chat",
        "max_tokens": 4096,
        "max_input_tokens": 16385,
        "input_cost_per_token": 0.0000005,
        "output_cost_per_token": 0.0000015,
        "supports_function_calling": True,
    },
    "claude-3-opus-20240229": {
        "litellm_provider": "anthropic",
        "mode": "chat",
        "max_tokens": 4096,
        "max_input_tokens": 200000,
        "input_cost_per_token": 0.000015,
        "output_cost_per_token": 0.000075,
        "supports_vision": True,
        "supports_function_calling": True,
    },
    "text-embedding-ada-002": {
        "litellm_provider": "openai",
        "mode": "embedding",
        "max_tokens": None,
        "max_input_tokens": 8191,
        "input_cost_per_token": 0.0000001,
        "output_cost_per_token": 0.0,
    },
    "dall-e-3": {
        "litellm_provider": "openai",
        "mode": "image_generation",
        "max_tokens": None,
        "max_input_tokens": None,
        "input_cost_per_token": 0.0,
        "output_cost_per_token": 0.0,
    },
}


@contextmanager
def patched_litellm_model_cost(model_cost: dict):
    fake_litellm = types.ModuleType("litellm")
    fake_litellm.model_cost = model_cost  # type: ignore[attr-defined]
    with patch.dict(sys.modules, {"litellm": fake_litellm}):
        yield
