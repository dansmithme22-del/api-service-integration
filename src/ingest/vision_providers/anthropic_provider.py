"""AnthropicProvider — Claude (Sonnet 4.5 / 4.6) vision.

Uses the ``anthropic`` Python SDK.  Claude is strong at structured JSON output
and architectural reasoning; the prompt asks for application/json and the
model honours that reliably.
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Optional

from .base import ModelChoice, VisionProvider

logger = logging.getLogger(__name__)


class AnthropicProvider(VisionProvider):
    name = "anthropic"
    default_models = ModelChoice(
        primary="claude-sonnet-4-5",
        fallback="claude-3-5-sonnet-latest",
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
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set.")
        try:
            import anthropic
        except ImportError as exc:
            raise ImportError(
                "anthropic SDK is required. Run: pip install anthropic"
            ) from exc

        client = anthropic.Anthropic(api_key=api_key)

        content_blocks: list[dict] = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": base64.standard_b64encode(image_bytes).decode("ascii"),
                },
            }
        ]
        if reference_bytes is not None:
            content_blocks.append({
                "type": "text",
                "text": (
                    "PRIMARY PLAN ↑ (above). Below is a REFERENCE plan "
                    "(likely a Matterport scan). Use the reference to verify "
                    "scale and proportions of the primary plan."
                ),
            })
            content_blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": base64.standard_b64encode(reference_bytes).decode("ascii"),
                },
            })
        content_blocks.append({"type": "text", "text": user_prompt})

        # Anthropic forces streaming when max_tokens is high enough that the
        # request might take > 10 min. We use streaming unconditionally for
        # parse_plan-sized outputs (16K) so we don't fight that limit.
        for model_name in (self.models.primary, self.models.fallback):
            try:
                if max_output_tokens > 8000:
                    text = self._stream_text(
                        client=client,
                        model=model_name,
                        max_tokens=max_output_tokens,
                        temperature=temperature,
                        system_prompt=system_prompt,
                        content_blocks=content_blocks,
                    )
                else:
                    resp = client.messages.create(
                        model=model_name,
                        max_tokens=max_output_tokens,
                        temperature=temperature,
                        system=system_prompt,
                        messages=[{"role": "user", "content": content_blocks}],
                    )
                    text = "".join(
                        b.text for b in resp.content
                        if getattr(b, "type", None) == "text"
                    ).strip()
                if text:
                    logger.info("Claude %s returned %d chars.", model_name, len(text))
                    return text
                logger.warning("Claude %s returned empty content.", model_name)
            except Exception as exc:
                logger.warning("Claude %s failed: %s", model_name, exc)
        raise RuntimeError("All Claude attempts failed.")

    def _stream_text(self, *, client, model: str, max_tokens: int,
                     temperature: float, system_prompt: str,
                     content_blocks: list) -> str:
        """Stream a Claude response, accumulate text deltas, return the full string."""
        parts: list[str] = []
        with client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": content_blocks}],
        ) as stream:
            for text in stream.text_stream:
                parts.append(text)
            final = stream.get_final_message()
            stop = getattr(final, "stop_reason", "?")
        logger.info("Claude stream stop_reason=%s, total chars=%d",
                    stop, sum(len(p) for p in parts))
        return "".join(parts).strip()
