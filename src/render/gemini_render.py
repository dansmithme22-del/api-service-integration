"""Send an Archicad view screenshot to Gemini 2.5 Flash Image for photoreal render.

The default style prompt favours architectural-presentation aesthetics (soft
daylight, realistic materials, no added geometry) — override per-call when
you want a different mood. The model preserves geometry well but will *add*
furnishings and lighting unless you constrain it; constraint is built into
the default prompt.

The Gemini 2.5 Flash Image model is invoked with the input image + a textual
edit prompt; it returns one image part which we write to disk.
"""

from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

logger = logging.getLogger(__name__)


class GeminiRenderError(RuntimeError):
    pass


DEFAULT_STYLE_PROMPT = (
    "Photorealistic architectural interior rendering. Soft natural daylight from "
    "windows, warm interior lighting, realistic materials and textures, "
    "professional architectural photography composition. "
    "Maintain the EXACT geometry, room layout, openings, and any furniture "
    "placement from the source image. Do not change walls or openings. "
    "Add realistic finishes, materials, lighting, and atmosphere consistent "
    "with a professional veterinary clinic interior."
)


@dataclass
class RenderJob:
    src: Path
    dst: Path
    style_prompt: str = DEFAULT_STYLE_PROMPT


def render_image(
    src: str | Path,
    dst: str | Path,
    *,
    style_prompt: str = DEFAULT_STYLE_PROMPT,
    model: str = "gemini-2.5-flash-image",
    max_retries: int = 2,
) -> Path:
    """Render a single image. Returns the destination path on success.

    Reads ``GEMINI_API_KEY`` from the environment (use a ``.env`` file via
    python-dotenv at script-entry time).
    """
    src = Path(src)
    dst = Path(dst)
    if not src.exists():
        raise FileNotFoundError(src)
    dst.parent.mkdir(parents=True, exist_ok=True)

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise GeminiRenderError("GEMINI_API_KEY is not set.")

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise GeminiRenderError(
            "google-genai is required. Run: pip install google-genai"
        ) from exc

    client = genai.Client(api_key=api_key)
    src_bytes = src.read_bytes()
    mime = _guess_mime(src)
    image_part = types.Part.from_bytes(data=src_bytes, mime_type=mime)

    last_exc: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            resp = client.models.generate_content(
                model=model,
                contents=[image_part, style_prompt],
            )
            out_bytes = _extract_image_bytes(resp)
            if not out_bytes:
                raise GeminiRenderError("Gemini returned no image data.")
            dst.write_bytes(out_bytes)
            logger.info("Rendered %s -> %s (%d bytes)", src.name, dst.name, len(out_bytes))
            return dst
        except Exception as exc:
            last_exc = exc
            wait = 2 ** attempt
            logger.warning(
                "Render attempt %d/%d failed: %s. Retrying in %ds.",
                attempt + 1, max_retries + 1, exc, wait,
            )
            time.sleep(wait)

    raise GeminiRenderError(f"All render attempts failed: {last_exc}")


def render_batch(
    jobs: Iterable[RenderJob],
    *,
    max_concurrent: int = 3,
    model: str = "gemini-2.5-flash-image",
) -> list[Path]:
    """Render multiple images in parallel. Returns successful destinations."""
    results: list[Path] = []
    jobs = list(jobs)

    with ThreadPoolExecutor(max_workers=max_concurrent) as pool:
        future_map = {
            pool.submit(
                render_image,
                job.src, job.dst,
                style_prompt=job.style_prompt,
                model=model,
            ): job
            for job in jobs
        }
        for fut in as_completed(future_map):
            job = future_map[fut]
            try:
                results.append(fut.result())
            except Exception as exc:
                logger.error("Job %s failed: %s", job.src.name, exc)
    return results


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _guess_mime(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(ext, "image/png")


def _extract_image_bytes(resp) -> Optional[bytes]:
    """Walk the Gemini response and pull out the first inline image part."""
    candidates = getattr(resp, "candidates", None) or []
    for cand in candidates:
        content = getattr(cand, "content", None)
        if content is None:
            continue
        parts = getattr(content, "parts", None) or []
        for part in parts:
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                return inline.data
            # Some SDK versions expose data directly on part.
            data = getattr(part, "data", None)
            if data:
                return data
    return None
