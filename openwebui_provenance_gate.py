"""
title: Provenance Gate
author: Vitaliy
description: Runtime guard for agent harnesses — a turn's PROVENANCE (who/what
  produced it) decides whether it may trigger an action. Stops the class of bug
  where a model fabricates a user approval ("yes, go ahead") and then executes
  autonomously on its own forged consent. Ships as an Open WebUI filter plus a
  helper, is_human_approval(), that action-tools call before any destructive step.
version: 0.1.0
required_open_webui_version: 0.5.0
license: MIT
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

# Approval tokens across a few languages, including the exact ones observed being
# *fabricated* in the wild (an agent invented the user replies "改吧" / "嗯" and ran
# with them). The point is NOT to blocklist these strings — it's that an approval
# counts only when it carries human-input provenance, whatever the wording.
DEFAULT_APPROVAL_PATTERNS = [
    r"\byes\b", r"\bok(ay)?\b", r"\bgo ahead\b", r"\bproceed\b", r"\bdo it\b",
    r"\bдавай\b", r"\bага\b", r"\bда\b",
    r"改吧", r"嗯", r"可以", r"好的",
]

HUMAN = "human_input"
MODEL = "model_generated"


def _content(m: dict) -> str:
    c = m.get("content", "")
    if isinstance(c, list):
        return " ".join(p.get("text", "") for p in c if isinstance(p, dict))
    return c if isinstance(c, str) else ""


def tag_provenance(messages: list[dict]) -> list[str]:
    """Label each turn by origin. In a role-separated transport (Open WebUI, chat
    APIs) a user turn can only come from a real input event; the assistant cannot
    author a user-role turn. We make that explicit so downstream gates rely on it
    instead of on the model's good behaviour."""
    return [HUMAN if m.get("role") == "user" else MODEL for m in (messages or [])]


def detect_fabricated_approval(messages: list[dict], patterns: list[str]) -> dict | None:
    """Heuristic TRIPWIRE (a signal, not ground truth): the latest assistant turn
    quotes/emits an approval as if it came from the user. This catches the single-
    stream fabrication pattern in harnesses that DON'T separate roles at the
    transport layer. Returns a flag dict or None.

    This is the tripwire, not the gate. The gate is provenance — see
    is_human_approval()."""
    if not messages or messages[-1].get("role") != "assistant":
        return None
    text = _content(messages[-1])
    for q in re.findall(r"[\"'「『“](.{1,40}?)[\"'」』”]", text):  # quoted/attributed lines
        for p in patterns:
            if re.search(p, q, re.IGNORECASE):
                return {
                    "flag": "fabricated_approval",
                    "quote": q.strip(),
                    "why": "assistant emitted a user-style approval; it has "
                           "model_generated provenance, not human_input",
                }
    return None


def is_human_approval(body: dict, user: dict | None,
                      owner_email: str | None = None) -> bool:
    """THE GATE. An action-tool calls this before any destructive step. True only
    if the triggering approval carries human-input provenance:
      (1) the initiator is a real authorised human (not the model), AND
      (2) the latest turn is an actual user turn (human_input), not the
          assistant's own text.
    A model-emitted "改吧" fails (2) by construction, so it never authorises an
    action — no matter how convincing the wording is."""
    u = user or {}
    if owner_email:
        authorised = (u.get("email") == owner_email) or (u.get("role") == "admin")
    else:
        authorised = (u.get("role") == "admin") or bool(u.get("id"))
    messages = body.get("messages", [])
    last_is_human = bool(messages) and messages[-1].get("role") == "user"
    return bool(authorised and last_is_human)


class Filter:
    """Open WebUI filter: tags turn provenance on the way in, and raises a tripwire
    if the assistant fabricates a user approval. Pair it with is_human_approval()
    inside your action-tools to gate execution on provenance, not on wording."""

    class Valves(BaseModel):
        owner_email: str = Field(
            default="",
            description="If set, only this email (or any admin) is a valid action "
                        "initiator. Empty = any signed-in user.")
        warn_on_fabrication: bool = Field(
            default=True,
            description="Surface a status warning when the assistant emits a "
                        "user-style approval inside its own turn.")
        approval_patterns: list[str] = Field(
            default_factory=lambda: list(DEFAULT_APPROVAL_PATTERNS),
            description="Approval tokens watched by the fabrication tripwire.")

    def __init__(self):
        self.valves = self.Valves()

    async def inlet(self, body: dict, __user__: dict | None = None,
                    __event_emitter__=None) -> dict:
        messages = body.get("messages", [])
        body.setdefault("metadata", {})["provenance"] = tag_provenance(messages)

        if self.valves.warn_on_fabrication and __event_emitter__:
            flag = detect_fabricated_approval(messages, self.valves.approval_patterns)
            if flag:
                await __event_emitter__({
                    "type": "status",
                    "data": {
                        "description": f"⚠ provenance: assistant emitted a "
                                       f"user-style approval (“{flag['quote']}”) — "
                                       f"not valid human consent.",
                        "done": True},
                })
        return body
