"""GeminiProvider — Google AI Studio (Gemini 2.5 Pro / Flash)."""

from __future__ import annotations

import logging
import os
from typing import Optional

from .base import ModelChoice, VisionProvider

logger = logging.getLogger(__name__)


class GeminiProvider(VisionProvider):
    name = "gemini"
    default_models = ModelChoice(
        primary="gemini-2.5-pro",
        fallback="gemini-2.5-flash",
    )

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
        return self._call(
            image_bytes=image_bytes,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            reference_bytes=reference_bytes,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )

    def refine_anchor(
        self,
        image_bytes: bytes,
        *,
        system_prompt: str,
        user_prompt: str = "Return the drawing-area bbox.",
    ) -> str:
        return self._call(
            image_bytes=image_bytes,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_output_tokens=2048,
            temperature=0.0,
        )

    # ------------------------------------------------------------------

    def _call(
        self,
        *,
        image_bytes: bytes,
        system_prompt: str,
        user_prompt: str,
        reference_bytes: Optional[bytes] = None,
        max_output_tokens: int = 32768,
        temperature: float = 0.1,
    ) -> str:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set.")
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise ImportError(
                "google-genai is required. Run: pip install google-genai"
            ) from exc

        client = genai.Client(api_key=api_key)

        image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/png")
        contents: list = [image_part]
        if reference_bytes is not None:
            ref_part = types.Part.from_bytes(data=reference_bytes, mime_type="image/png")
            contents.extend([
                "PRIMARY PLAN ↑ (above). Below is a REFERENCE plan (likely a "
                "Matterport scan) showing the same building with accurate "
                "dimensions. Use the reference to verify scale, proportions, "
                "and overall extents.",
                ref_part,
            ])
        contents.append(user_prompt)

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

        for model_name in (self.models.primary, self.models.fallback):
            try:
                resp = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config,
                )
                text = (resp.text or "").strip()
                if text:
                    logger.info("Gemini %s returned %d chars.", model_name, len(text))
                    return text
                logger.warning("Gemini %s returned empty text.", model_name)
            except Exception as exc:
                logger.warning("Gemini %s failed: %s", model_name, exc)
        raise RuntimeError("All Gemini attempts failed.")
