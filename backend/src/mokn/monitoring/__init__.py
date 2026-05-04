"""Proactive monitoring layer.

Sits outside the negotiation loop. `risk_rules` is pure Python (deterministic,
trivially testable) and `scanner` orchestrates a sweep of all students, asking
the GuardianAgent to translate each non-trivial RiskAssessment into Arabic
prose suitable for the student.
"""
