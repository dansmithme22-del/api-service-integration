"""OpenAIProvider — OpenAI GPT-4o / GPT-4.1 vision."""

from __future__ import annotations

import base64
import logging
import os
from typing import Optional

from .base import ModelChoice, VisionProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(VisionProvider):
    name = "openai"
    default_models = ModelChoice(
        primary="gpt-4.1",
        fallback="gpt-4o",
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
            json_mode=True,
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
            json_mode=True,
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
        json_mode: bool = True,
    ) -> str:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set.")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError(
                "openai SDK is required. Run: pip install openai"
            ) from exc

        client = OpenAI(api_key=api_key)

        def _img(b: bytes) -> dict:
            return {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/png;base64,"
                           + base64.standard_b64encode(b).decode("ascii"),
                    "detail": "high",
                },
            }

        user_content: list[dict] = [_img(image_bytes)]
        if reference_bytes is not None:
            user_content.append({
                "type": "text",
                "text": (
                    "PRIMARY PLAN above. Below is a REFERENCE plan "
                    "(likely Matterport). Use it to verify scale and proportions."
                ),
            })
            user_content.append(_img(reference_bytes))
        user_content.append({"type": "text", "text": user_prompt})

        kwargs: dict = {
            "max_tokens": max_output_tokens,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        for model_name in (self.models.primary, self.models.fallback):
            try:
                resp = client.chat.completions.create(model=model_name, **kwargs)
                text = (resp.choices[0].message.content or "").strip()
                if text:
                    logger.info("OpenAI %s returned %d chars.", model_name, len(text))
                    return text
                logger.warning("OpenAI %s returned empty content.", model_name)
            except Exception as exc:
                logger.warning("OpenAI %s failed: %s", model_name, exc)
        raise RuntimeError("All OpenAI attempts failed.")
