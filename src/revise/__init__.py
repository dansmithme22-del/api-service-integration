"""Natural-language revision requests -> PlanGraph edits.

Given a PlanGraph (the existing model) plus a free-text revision request
(e.g. "remove the wall between Treatment 1 and Treatment 2, add a 36-inch
door between Reception and Office"), produce a new PlanGraph plus a
ChangeLog describing what changed.

The revision interpreter uses Gemini with structured output. It must NEVER
silently alter geometry it wasn't asked to touch.
"""

from .interpreter import apply_revision_request, ChangeLog, ChangeEntry

__all__ = ["apply_revision_request", "ChangeLog", "ChangeEntry"]
