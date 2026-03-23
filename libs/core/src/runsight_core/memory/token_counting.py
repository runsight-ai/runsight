"""
Default litellm-based TokenCounter adapter.

This module provides a concrete implementation of the TokenCounter protocol
using litellm's token_counter function.
"""

from litellm import token_counter


def litellm_token_counter(text: str, model: str) -> int:
    """Count tokens using litellm's token_counter."""
    return token_counter(model=model, text=text)
