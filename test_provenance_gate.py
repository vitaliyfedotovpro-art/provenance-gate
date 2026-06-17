"""Smoke test — the gate must hold on the exact failure shape from CodeWhale #3275:
a model fabricates a user approval ("改吧") and tries to proceed."""
from openwebui_provenance_gate import (
    tag_provenance, detect_fabricated_approval, is_human_approval,
    DEFAULT_APPROVAL_PATTERNS, HUMAN, MODEL,
)

oks, fails = [], []
def ok(m): oks.append(m); print(" ✓", m)
def bad(m): fails.append(m); print(" ✗", m)

# 1) provenance tagging follows roles
msgs = [{"role": "user", "content": "check cart i18n"},
        {"role": "assistant", "content": "scanning..."}]
assert tag_provenance(msgs) == [HUMAN, MODEL]
ok("tag_provenance maps user->human_input, assistant->model_generated")

# 2) real human approval passes the gate
human_yes = msgs + [{"role": "user", "content": "yes, go ahead"}]
if is_human_approval({"messages": human_yes}, {"role": "admin"}):
    ok("real user approval + authorised initiator -> gate OPEN")
else:
    bad("human approval was wrongly refused")

# 3) #3275: assistant fabricates the user's approval, then 'proceeds'
forged = msgs + [{"role": "assistant",
                  "content": 'User said "改吧", so I will continue across 75 files.'}]
if not is_human_approval({"messages": forged}, {"role": "admin"}):
    ok("forged approval in an assistant turn -> gate REFUSES (last turn not human)")
else:
    bad("forged approval slipped through the gate")

# 4) tripwire flags the fabrication as a signal
flag = detect_fabricated_approval(forged, DEFAULT_APPROVAL_PATTERNS)
if flag and flag["flag"] == "fabricated_approval" and "改吧" in flag["quote"]:
    ok(f"tripwire caught fabricated approval: “{flag['quote']}”")
else:
    bad(f"tripwire missed the fabrication: {flag}")

# 5) unauthorised initiator can't act even on a real user turn
if not is_human_approval({"messages": human_yes}, {"role": "user"}, owner_email="owner@x"):
    ok("authorised-initiator check holds (non-owner, non-admin -> refused)")
else:
    bad("unauthorised initiator passed")

print(f"\n==== {len(oks)} ok / {len(fails)} fail ====")
raise SystemExit(1 if fails else 0)
