"""Lightweight annotator glue — the UI does most of the work.

This module provides CSV I/O for gold flags so the annotator tab in the UI can import/export
without the UI knowing the pydantic schema directly.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .schemas import GoldFlag


def load_gold_csv(path: Path) -> list[GoldFlag]:
    df = pd.read_csv(path)
    return [GoldFlag(**row) for _, row in df.iterrows()]


def save_gold_csv(flags: list[GoldFlag], path: Path) -> None:
    pd.DataFrame([f.model_dump() for f in flags]).to_csv(path, index=False)
