"""View capture + Gemini photorealistic rendering.

Two-step flow:

1. ``view_capturer.export_views`` — pulls 2D/3D views from the running
   Archicad project (or accepts pre-exported PNGs) into a working directory.
2. ``gemini_render.render_image`` — sends each captured PNG through
   Gemini 2.5 Flash Image with a style prompt; saves a photorealistic
   version next to the original.
"""

from .gemini_render import render_image, render_batch, GeminiRenderError
from .view_capturer import export_views, ViewExportError

__all__ = [
    "render_image",
    "render_batch",
    "GeminiRenderError",
    "export_views",
    "ViewExportError",
]
