"""Planning-domain exceptions.

Distinguishes "the solver could not assemble a valid schedule" from generic
errors so the agent layer can return a structured `no_solution` proposal
instead of pretending an empty schedule is valid.
"""
from __future__ import annotations


class InsufficientCoursesError(Exception):
    """Raised when no candidate satisfies the constraints (notably min_credits).

    Carries the responsible student id and a short rationale so the Planner
    can build an honest user-facing message instead of a generic refusal.
    """

    def __init__(
        self,
        message: str,
        *,
        student_id: str | None = None,
        eligible_credits: int | None = None,
        min_required: int | None = None,
    ) -> None:
        super().__init__(message)
        self.student_id = student_id
        self.eligible_credits = eligible_credits
        self.min_required = min_required
