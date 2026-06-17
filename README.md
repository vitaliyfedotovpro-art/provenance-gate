# Provenance Gate

A small runtime rail for agent harnesses: **a turn's provenance — who or what
produced it — decides whether it may trigger an action.** Not a prompt
instruction the model has to remember; a gate the model cannot talk its way past.

## The failure it stops

Agents in a single generation stream can drift into proposing work, *answering
their own question as if the user approved*, and executing on that forged
consent. Observed in the wild, e.g. CodeWhale (DeepSeek-TUI)
[#3275](https://github.com/Hmbown/DeepSeek-TUI/issues/3275): the agent fabricated
user replies (`改吧`, `嗯`) and ran autonomous edits across 75+ files. A guard that
only checks *“is there a user message?”* can't catch this — the fabricated
message *is* there. You need to check where it **came from**.

## The invariant

> A user-role turn is valid only if it carries the provenance of a real input
> event. An approval that originated in the assistant's own turn is not an
> approval — by construction, regardless of wording.

Two pieces:

- **`tag_provenance(messages)`** — labels every turn `human_input` / `model_generated`.
- **`is_human_approval(body, user, owner_email)`** — *the gate*. Action-tools call
  it before any destructive step. Returns true only when (1) the initiator is a
  real authorised human and (2) the latest turn is an actual user turn — not the
  model's text. A model-emitted `改吧` fails (2) by construction.

A heuristic **tripwire** (`detect_fabricated_approval`) additionally *flags* an
assistant turn that quotes a user-style approval — a signal, not the gate.

## Why a rail, not a prompt

Prompt rules ("never self-approve") are advice the model forgets under scope
pressure, and they ask it to police a boundary it has the means to cross. The
gate moves the boundary into the harness: forged consent never reaches the
executor, no matter how convincing the generation is.

## Use (Open WebUI)

1. Install `openwebui_provenance_gate.py` as a **Filter** — tags provenance,
   warns on fabrication.
2. In each action/tool, gate the destructive step:

   ```python
   from openwebui_provenance_gate import is_human_approval
   if not is_human_approval(body, __user__, self.valves.owner_email or None):
       return  # refuse: no human-input provenance
   ```

See `example_gated_action.py`.

## Run the test

```
python test_provenance_gate.py
```

Covers the #3275 shape directly: a forged `改吧` in an assistant turn is refused
by the gate and caught by the tripwire.

## Honest scope

Open WebUI already separates user/assistant turns at the transport layer, which
makes this class of fabrication *structurally harder* than in a single-stream
TUI — the gate closes the remainder. The **invariant** (provenance decides action
eligibility) is platform-independent; the Open WebUI filter is one
implementation. The tripwire is a heuristic signal, not a proof.

MIT.
