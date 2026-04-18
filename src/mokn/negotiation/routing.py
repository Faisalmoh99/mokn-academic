"""Conditional-edge functions for the LangGraph negotiation graph.

Kept pure (no I/O, no LLM, no side effects) so LangGraph can call them
whenever it wants to pick the next node. Mutations happen only inside the
node functions in `nodes.py`.
"""
from __future__ import annotations

from mokn.negotiation.state import NegotiationState


def route_after_classify(state: NegotiationState) -> str:
    """Pick the first real action based on the classifier's verdict."""
    intent = state.get("intent", "unknown")
    if intent == "regulation_question":
        return "legis_only"
    if intent == "build_schedule":
        return "fetch_student"
    return "synthesize"


def route_after_review(state: NegotiationState) -> str:
    """After Legis reviews a proposal, decide: approve, retry, or escalate."""
    turns = state.get("turns", [])
    if not turns:
        return "synthesize"
    last = turns[-1]
    turn_type = last.get("turn_type")

    if turn_type == "legis_approve":
        return "synthesize"

    # Veto path.
    round_number = state.get("round_number", 1)
    max_rounds = state.get("max_rounds", 3)
    if round_number >= max_rounds:
        return "synthesize"  # caller sets outcome=escalated
    return "planner_propose"
