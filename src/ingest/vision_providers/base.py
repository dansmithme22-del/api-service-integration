"""Abstract vision-provider interface.

Each provider must implement two methods:

  parse_plan(image_bytes, system_prompt, user_prompt, *, reference_bytes,
             max_output_tokens, temperature) -> str
      Send one or two images + prompts to the underlying model; return the
      RAW text/JSON response.  The caller will parse it.

  refine_anchor(image_bytes, system_prompt, user_prompt) -> str
      Cheaper focused call asking ONLY for the drawing-area anchor bbox.

The abstraction lets the rest of the pipeline stay model-agnostic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class ModelChoice:
    primary: str            # e.g. "gemini-2.5-pro"
    fallback: str           # e.g. "gemini-2.5-flash"


class VisionProvider(ABC):
    """Base class for vision providers."""

    name: str = "abstract"
    default_models: ModelChoice = ModelChoice(primary="", fallback="")

    def __init__(self, models: Optional[ModelChoice] = None):
        self.models = models or self.default_models

    @abstractmethod
    def parse_plan(
        self,
        image_bytes: bytes,
        *,
        system_prompt: str,
        user_prompt: str = "Return the JSON plan description for this floor plan.",
        reference_bytes: Optional[bytes] = None,
        max_output_tokens: int = 32768,
        temperature: float = 0.1,
    ) -> str:
        """Return raw text/JSON from the model."""

    @abstractmethod
    def refine_anchor(
        self,
        image_bytes: bytes,
        *,
        system_prompt: str,
        user_prompt: str = "Return the drawing-area bbox.",
    ) -> str:
        """Return raw text/JSON for a focused anchor-bbox call."""
