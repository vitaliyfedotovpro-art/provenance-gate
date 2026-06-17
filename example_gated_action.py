"""
title: Example — Gated Executor
author: Vitaliy
description: Minimal Open WebUI action showing how an executor tool consults the
  provenance gate before doing anything destructive. The model cannot authorise
  this action by writing "yes" in its own turn — only a real user turn can.
version: 0.1.0
required_open_webui_version: 0.5.0
license: MIT
"""

from pydantic import BaseModel, Field

# In a real install, import from the published module:
#   from openwebui_provenance_gate import is_human_approval
from openwebui_provenance_gate import is_human_approval


class Action:
    class Valves(BaseModel):
        owner_email: str = Field(
            default="", description="Only this email (or any admin) may run the executor.")

    def __init__(self):
        self.valves = self.Valves()

    async def _status(self, emit, text):
        if emit:
            await emit({"type": "status", "data": {"description": text, "done": True}})

    async def action(self, body, __user__=None, __event_emitter__=None, __event_call__=None):
        emit = __event_emitter__

        # THE GATE — provenance, not wording. A model-fabricated "改吧" / "yes"
        # lives in an assistant turn, so it fails is_human_approval() by
        # construction and never reaches the destructive step below.
        if not is_human_approval(body, __user__, self.valves.owner_email or None):
            return await self._status(
                emit, "⛔ Refused: no human-input provenance for this action. "
                      "An approval must come from a real user turn, not the model's own text.")

        # ... destructive step (run shell, write files, git push, spawn agents) ...
        await self._status(emit, "✅ Authorised by human provenance — executing.")
