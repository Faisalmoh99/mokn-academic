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


def route_after_propose(state: NegotiationState) -> str:
    """Skip Legis when Planner reported no_solution.

    Handing an empty proposal to Legis guarantees a pointless veto for being
    below the credit-hour floor — that was the symptom we're fixing here.
    """
    if _proposal_no_solution(state.get("current_proposal")):
        return "synthesize"
    return "legis_review"


def _proposal_no_solution(proposal: object) -> bool:
    if proposal is None:
        return False
    if isinstance(proposal, dict):
        return bool(proposal.get("no_solution"))
    return bool(getattr(proposal, "no_solution", False))


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
