"""
Shared LLM factory for all agents.
Uses OpenRouter so a single API key gives access to GPT-4o, Claude, and Llama.
"""

import os
from langchain_openai import ChatOpenAI

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-4o-mini"


def get_llm(model: str | None = None, temperature: float = 0) -> ChatOpenAI:
    """
    Return a LangChain ChatOpenAI client pointed at OpenRouter.

    Args:
        model: OpenRouter model ID (e.g. "openai/gpt-4o",
               "anthropic/claude-3.5-sonnet", "meta-llama/llama-3.1-70b-instruct").
               Falls back to LLM_MODEL env var, then DEFAULT_MODEL.
        temperature: Sampling temperature (0 = deterministic).
    """
    resolved_model = model or os.environ.get("LLM_MODEL", DEFAULT_MODEL)
    return ChatOpenAI(
        model=resolved_model,
        temperature=temperature,
        openai_api_key=os.environ["OPENROUTER_API_KEY"],
        openai_api_base=OPENROUTER_BASE,
        default_headers={
            "HTTP-Referer": "https://github.com/ParthGala2k/AuditTrace",
            "X-Title": "AuditTrace",
        },
    )
