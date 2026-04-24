"""Unit tests for `_sanitize_schema_for_gemini`.

Gemini's structured-output validator rejects `additionalProperties` even
though Pydantic v2 emits it by default. The sanitizer must strip it
wherever it appears, without altering anything else.
"""
from __future__ import annotations

from mokn.llm.gemini import _sanitize_schema_for_gemini


def test_strips_top_level_additional_properties() -> None:
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "additionalProperties": False,
    }
    out = _sanitize_schema_for_gemini(schema)
    assert "additionalProperties" not in out
    assert out == {"type": "object", "properties": {"name": {"type": "string"}}}


def test_strips_nested_additional_properties_inside_properties() -> None:
    schema = {
        "type": "object",
        "properties": {
            "foo": {
                "type": "object",
                "properties": {"x": {"type": "integer"}},
                "additionalProperties": False,
            }
        },
        "additionalProperties": False,
    }
    out = _sanitize_schema_for_gemini(schema)
    assert "additionalProperties" not in out
    assert "additionalProperties" not in out["properties"]["foo"]
    assert out["properties"]["foo"]["properties"] == {"x": {"type": "integer"}}


def test_strips_additional_properties_inside_items_array() -> None:
    schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "additionalProperties": False,
        },
    }
    out = _sanitize_schema_for_gemini(schema)
    assert "additionalProperties" not in out["items"]
    assert out["items"]["properties"] == {"code": {"type": "string"}}


def test_strips_additional_properties_from_dict_mapping() -> None:
    # Pydantic renders `dict[str, str]` with a schema-valued additionalProperties.
    schema = {
        "type": "object",
        "additionalProperties": {"type": "string"},
    }
    out = _sanitize_schema_for_gemini(schema)
    assert out == {"type": "object"}


def test_untouched_when_no_additional_properties() -> None:
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["name"],
    }
    assert _sanitize_schema_for_gemini(schema) == schema


def test_non_dict_non_list_passes_through() -> None:
    assert _sanitize_schema_for_gemini("string") == "string"
    assert _sanitize_schema_for_gemini(42) == 42
    assert _sanitize_schema_for_gemini(None) is None
    assert _sanitize_schema_for_gemini(True) is True


def test_strips_through_defs_and_refs() -> None:
    # Pydantic v2 uses $defs for nested models — sanitizer must descend.
    schema = {
        "$defs": {
            "Citation": {
                "type": "object",
                "properties": {"source": {"type": "string"}},
                "additionalProperties": False,
            }
        },
        "type": "object",
        "properties": {
            "citations": {"type": "array", "items": {"$ref": "#/$defs/Citation"}}
        },
        "additionalProperties": False,
    }
    out = _sanitize_schema_for_gemini(schema)
    assert "additionalProperties" not in out
    assert "additionalProperties" not in out["$defs"]["Citation"]
    # $ref is preserved.
    assert out["properties"]["citations"]["items"] == {"$ref": "#/$defs/Citation"}


def test_sanitized_planner_decision_is_gemini_compatible() -> None:
    """End-to-end sanity: the real `_PlannerDecision` schema round-trips clean."""
    from mokn.agents.planner import _PlannerDecision

    raw = _PlannerDecision.model_json_schema()
    cleaned = _sanitize_schema_for_gemini(raw)

    def _walk(node: object) -> None:
        if isinstance(node, dict):
            assert "additionalProperties" not in node
            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(cleaned)
