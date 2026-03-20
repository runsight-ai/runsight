"""
Token windowing utility for pruning conversation history to fit model context limits.
"""

from litellm import get_model_info, token_counter

_FALLBACK_MAX_TOKENS = 4096
_BUDGET_RATIO = 0.9


def get_max_tokens(model: str) -> int:
    """Return the usable token budget for *model* (90% of max_input_tokens).

    Falls back to 4096 if the model is unknown or lookup fails.
    """
    try:
        info = get_model_info(model)
        return int(info["max_input_tokens"] * _BUDGET_RATIO)
    except Exception:
        return _FALLBACK_MAX_TOKENS


def prune_messages(messages: list[dict], max_tokens: int, model: str) -> list[dict]:
    """Remove oldest user/assistant pairs until total tokens <= *max_tokens*.

    Rules:
    - Removes pairs (2 messages) from the front (FIFO).
    - A single remaining message/pair that still exceeds the budget is returned as-is.
    - Empty input returns an empty list.
    """
    if not messages:
        return []

    msgs = list(messages)

    while len(msgs) > 2:
        count = token_counter(model=model, messages=msgs)
        if count <= max_tokens:
            return msgs
        msgs = msgs[2:]

    # Last pair (or single message) — return as-is regardless of token count
    return msgs
