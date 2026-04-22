"""Central configuration for TAD.

Every config parameter has a matching entry in app/explanations/params.yaml.
Startup fails loudly if any enabled param lacks an explanation (checked by explain.py).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

try:
    import streamlit as st
    _HAS_STREAMLIT = True
except ImportError:
    _HAS_STREAMLIT = False

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent


def _get_api_key() -> str:
    """Resolve API key from (1) env var, (2) streamlit secrets, (3) hardcoded fallback from spec."""
    key = os.getenv("GOOGLE_API_KEY")
    if key:
        return key
    if _HAS_STREAMLIT:
        try:
            if "GOOGLE_API_KEY" in st.secrets:
                return st.secrets["GOOGLE_API_KEY"]
        except Exception:
            pass
    # Spec-provided fallback (user explicitly authorised).
    return "AIzaSyC0wd3ShnKJDQCLGwL_9hVaDirsuQZIhBU"


GOOGLE_API_KEY: str = _get_api_key()

# Models
DETECTION_MODEL: str = "gemini-2.5-flash"
ADJUDICATION_MODEL: str = "gemini-2.5-pro"
JUDGE_MODEL: str = "gemini-2.5-pro"
REWRITE_MODEL: str = "gemini-2.5-pro"
EXTRACTION_MODEL: str = "gemini-2.5-flash"
EMBEDDING_MODEL: str = "text-embedding-004"

# Storage
CHROMA_DIR: Path = ROOT / "chroma_store"
OUTPUT_DIR: Path = ROOT / "output"
CHROMA_DIR.mkdir(exist_ok=True, parents=True)
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

# Retrieval
TOP_K_TENDER: int = 5
TOP_K_ISCODE: int = 5

# Chunking
CHUNK_MAX_TOKENS: int = 500
CHUNK_OVERLAP: int = 50

# Detection ensemble (guardrail G1)
DETECTION_AGREEMENT_THRESHOLD: int = 2  # out of 3 passes
SPAN_IOU_THRESHOLD: float = 0.5

# Concurrency / retries
MAX_CONCURRENT_LLM_CALLS: int = 4
LLM_MAX_RETRIES: int = 3
LLM_RETRY_BASE_S: float = 2.0

# Reproducibility
RANDOM_SEED: int = 1729

# Categories
ENABLED_CATEGORIES: list[str] = ["F", "B", "I", "A", "E", "G", "H", "J"]
GRAPH_CATEGORIES: list[str] = ["G", "H"]  # routed to graph retrieval

CATEGORY_NAMES: Dict[str, str] = {
    "F": "Undefined technical terms",
    "B": "Vague qualitative adjectives",
    "I": "Missing reference targets",
    "A": "Lexical ambiguity",
    "E": "Anaphoric ambiguity",
    "G": "Cross-document priority conflict",
    "H": "Cross-document numerical inconsistency",
    "J": "Incomplete specifications",
}

# Default per-category confidence thresholds (overridden by calibration.json after calibration sweep).
_DEFAULT_DETECTION_THRESHOLDS: Dict[str, float] = {
    "F": 0.55,
    "B": 0.55,
    "I": 0.60,
    "A": 0.60,
    "E": 0.55,
    "G": 0.60,
    "H": 0.60,
    "J": 0.55,
}


def load_detection_thresholds() -> Dict[str, float]:
    calib = OUTPUT_DIR / "calibration.json"
    if calib.exists():
        try:
            data = json.loads(calib.read_text())
            if isinstance(data, dict):
                out = dict(_DEFAULT_DETECTION_THRESHOLDS)
                for k, v in data.items():
                    if k in out and isinstance(v, (int, float)):
                        out[k] = float(v)
                return out
        except Exception:
            pass
    return dict(_DEFAULT_DETECTION_THRESHOLDS)


DETECTION_CONFIDENCE_THRESHOLD: Dict[str, float] = load_detection_thresholds()


def dump() -> Dict[str, Any]:
    """Serialise config for UI display / run manifest."""
    return {
        "DETECTION_MODEL": DETECTION_MODEL,
        "ADJUDICATION_MODEL": ADJUDICATION_MODEL,
        "JUDGE_MODEL": JUDGE_MODEL,
        "REWRITE_MODEL": REWRITE_MODEL,
        "EXTRACTION_MODEL": EXTRACTION_MODEL,
        "EMBEDDING_MODEL": EMBEDDING_MODEL,
        "TOP_K_TENDER": TOP_K_TENDER,
        "TOP_K_ISCODE": TOP_K_ISCODE,
        "CHUNK_MAX_TOKENS": CHUNK_MAX_TOKENS,
        "CHUNK_OVERLAP": CHUNK_OVERLAP,
        "DETECTION_AGREEMENT_THRESHOLD": DETECTION_AGREEMENT_THRESHOLD,
        "SPAN_IOU_THRESHOLD": SPAN_IOU_THRESHOLD,
        "DETECTION_CONFIDENCE_THRESHOLD": DETECTION_CONFIDENCE_THRESHOLD,
        "RANDOM_SEED": RANDOM_SEED,
        "ENABLED_CATEGORIES": ENABLED_CATEGORIES,
        "GRAPH_CATEGORIES": GRAPH_CATEGORIES,
    }
