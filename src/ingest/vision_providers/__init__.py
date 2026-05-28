"""Pluggable vision-provider abstraction for the ingest pipeline.

Three providers are supported out of the box:

  * ``gemini``     — Google AI Studio (Gemini 2.5 Pro / Flash)
  * ``anthropic``  — Anthropic Claude (Sonnet)
  * ``openai``     — OpenAI GPT-4o / GPT-4.1

Selection precedence (highest first):
  1. Explicit ``provider`` arg on ``get_provider()``
  2. ``VISION_PROVIDER`` environment variable
  3. First provider whose API key is present in the environment

Each concrete provider implements :class:`VisionProvider.parse_plan` and
:class:`VisionProvider.refine_anchor`.  They return raw JSON text — the
existing parser/normalizer turns that into a PlanGraph.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from .anthropic_provider import AnthropicProvider
from .base import VisionProvider
from .gemini_provider import GeminiProvider
from .openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


PROVIDERS: dict[str, type[VisionProvider]] = {
    "gemini": GeminiProvider,
    "anthropic": AnthropicProvider,
    "claude": AnthropicProvider,
    "openai": OpenAIProvider,
    "gpt-4o": OpenAIProvider,
}


def get_provider(name: Optional[str] = None, **kwargs) -> VisionProvider:
    """Return a configured VisionProvider instance.

    Resolution:
      1. ``name`` argument (e.g. "anthropic")
      2. ``VISION_PROVIDER`` env var
      3. Auto-detect from which key is present
    """
    requested = (name or os.environ.get("VISION_PROVIDER") or "").strip().lower()
    if requested and requested in PROVIDERS:
        cls = PROVIDERS[requested]
        logger.info("Using vision provider: %s", cls.name)
        return cls(**kwargs)
    if requested:
        raise ValueError(
            f"Unknown VISION_PROVIDER={requested!r}. "
            f"Valid: {sorted(set(PROVIDERS.keys()))}"
        )

    # Auto-detect.
    for env_key, cls_name in (
        ("ANTHROPIC_API_KEY", "anthropic"),
        ("OPENAI_API_KEY", "openai"),
        ("GEMINI_API_KEY", "gemini"),
    ):
        if os.environ.get(env_key):
            cls = PROVIDERS[cls_name]
            logger.info("Auto-detected vision provider %s (via %s).", cls.name, env_key)
            return cls(**kwargs)

    raise RuntimeError(
        "No vision provider configured. Set one of GEMINI_API_KEY, "
        "ANTHROPIC_API_KEY, or OPENAI_API_KEY in your .env, or pass "
        "--vision-provider on the CLI."
    )


__all__ = [
    "VisionProvider",
    "GeminiProvider",
    "AnthropicProvider",
    "OpenAIProvider",
    "get_provider",
    "PROVIDERS",
]
