def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    pricing: dict | None,
) -> float:
    """
    Returns cost in USD. Returns 0.0 if pricing is None or missing fields.
    Never raises.
    """
    if pricing is None:
        return 0.0
    try:
        input_per_m = pricing.get("input_per_million", 0.0)
        output_per_m = pricing.get("output_per_million", 0.0)
        cost = (input_tokens * input_per_m / 1_000_000) + (
            output_tokens * output_per_m / 1_000_000
        )
        return cost
    except Exception:
        return 0.0


def estimate_tokens(messages: list[dict], system_prompt: str | None = None) -> int:
    """
    Rough token estimate: total character count of all content / 4.
    Used for pre-call context limit checks only — not for billing.
    Never raises.
    """
    try:
        total_chars = 0
        if system_prompt:
            total_chars += len(system_prompt)
        for msg in messages:
            content = msg.get("content", "")
            total_chars += len(content)
        return total_chars // 4
    except Exception:
        return 0
