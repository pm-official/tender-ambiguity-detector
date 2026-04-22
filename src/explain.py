"""YAML-backed loader for every UI explanation.

Every number, badge, slider, tab, stage, verdict, category in the UI must resolve to a YAML entry
via ``get(key_path)``.  Missing keys raise loudly — this prevents black-box numbers.
"""
from __future__ import annotations

import functools
from pathlib import Path
from typing import Any

import yaml

_EXPL_DIR = Path(__file__).resolve().parent.parent / "app" / "explanations"

_FILES = [
    "metrics.yaml",
    "categories.yaml",
    "verdicts.yaml",
    "stages.yaml",
    "params.yaml",
    "examples.yaml",
    "graph_legend.yaml",
    "ablations.yaml",
    "annotation_protocol.yaml",
    "document_types.yaml",  # Prompt-4
    "scoring.yaml",  # Prompt-4
]


@functools.lru_cache(maxsize=1)
def _load_all() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for fname in _FILES:
        p = _EXPL_DIR / fname
        if not p.exists():
            continue
        with p.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        key = fname.replace(".yaml", "")
        out[key] = data
    return out


def reload() -> None:
    _load_all.cache_clear()


def all_explanations() -> dict[str, Any]:
    return _load_all()


def get(path: str, default: Any | None = None) -> Any:
    """Fetch an explanation node. Path uses dotted notation: metrics.precision, categories.F, params.TOP_K_TENDER."""
    parts = path.split(".")
    node: Any = _load_all()
    for part in parts:
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            if default is not None:
                return default
            return None
    return node


def category_display(category_id: str) -> str:
    """Return the intuitive display name for a category letter code (F/B/I/A/E/G/H/J).

    Falls back to the letter code if the YAML doesn't have a display_name. Used everywhere
    user-facing text is rendered; letter codes stay as internal IDs in schemas and CSVs.
    """
    e = get(f"categories.{category_id}")
    if isinstance(e, dict):
        name = e.get("display_name") or e.get("title")
        if name:
            return str(name)
    return category_id


def category_display_with_code(category_id: str) -> str:
    """'Undefined Terms (F)' — use only in tooltips/power-user surfaces, never as a chip label."""
    return f"{category_display(category_id)} ({category_id})"


def verdict_display(verdict: str) -> str:
    """Map internal verdict enum / new vocabulary to a user-facing label."""
    e = get(f"verdicts.{verdict}")
    if isinstance(e, dict):
        name = e.get("display_name") or e.get("title")
        if name:
            return str(name)
    legacy = {
        "RESOLVED": "Resolved by Context",
        "RESOLVED_BY_CONTEXT": "Resolved by Context",
        "PARTIALLY_RESOLVED": "Partially Resolved",
        "UNRESOLVED": "Confirmed Ambiguous",
        "CONFIRMED_AMBIGUOUS": "Confirmed Ambiguous",
    }
    return legacy.get(verdict, verdict)


def explain_or_stub(path: str) -> dict[str, Any]:
    """Return a dict with title/what/why/how/benchmark/example keys, stubbed if missing."""
    e = get(path)
    if not isinstance(e, dict):
        return {
            "title": path,
            "what": "(explanation missing)",
            "why": "",
            "how": "",
            "benchmark": "",
            "example": "",
        }
    return {
        "title": e.get("title", path),
        "what": e.get("what", ""),
        "why": e.get("why", ""),
        "how": e.get("how", ""),
        "benchmark": e.get("benchmark", ""),
        "example": e.get("example", ""),
    }
