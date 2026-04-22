"""Quantity extractor for the Numerical Inconsistencies (H) graph.

Extracts numeric quantities from a chunk with a canonicalised "name" so the graph can
compare the same quantity across different documents.

Examples:
  "M25 concrete"                 -> QuantityMention(name="concrete_grade", value="M25", ...)
  "Fe500 steel"                  -> QuantityMention(name="steel_grade", value="Fe500", ...)
  "28 days cube strength"        -> QuantityMention(name="cube_strength_age_days", value=28)
  "+/- 5 mm tolerance"           -> QuantityMention(name="tolerance_mm", value=5)
  "minimum 20 MPa"               -> QuantityMention(name="strength_MPa", value=20)
  "1200 cu.m of concrete"        -> QuantityMention(name="concrete_volume_cu.m", value=1200)
  "Rs. 4.50 crore"               -> QuantityMention(name="amount_crore_rs", value=4.5)
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

UNIT_MAP = {
    "cu.m": "cu.m", "cum": "cu.m", "cubic metre": "cu.m", "m3": "cu.m",
    "sq.m": "sq.m", "sqm": "sq.m", "square metre": "sq.m", "m2": "sq.m",
    "tonne": "tonne", "tonnes": "tonne", "mt": "tonne",
    "mm": "mm", "cm": "cm", "m": "m",
    "mpa": "MPa", "n/mm2": "MPa", "n/mm²": "MPa",
    "kg": "kg",
}


@dataclass
class QuantityMention:
    raw: str
    name: str
    value: object
    unit: str | None
    span_start: int
    span_end: int

    def to_dict(self) -> dict:
        return asdict(self)


_GRADE_CONCRETE = re.compile(r"\bM\s?(\d{2,3})\b")
_GRADE_STEEL = re.compile(r"\b(Fe\s?\d{3,4})\b", re.IGNORECASE)
_CRORE = re.compile(r"(?:Rs\.?|INR)\s*([0-9]+(?:\.[0-9]+)?)\s*(?:crore|cr)\b", re.IGNORECASE)
_LAKH = re.compile(r"(?:Rs\.?|INR)\s*([0-9]+(?:\.[0-9]+)?)\s*(?:lakh|lac)\b", re.IGNORECASE)
_AGE_DAYS = re.compile(r"(\d{1,3})\s*(?:day|days|d)\b", re.IGNORECASE)
_STRENGTH = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*(?:MPa|N/mm2|N/mm²)\b", re.IGNORECASE)
_TOLERANCE = re.compile(r"(?:±|\+/-|\+/\-)\s*(\d{1,3}(?:\.\d+)?)\s*(mm|cm|m|%)", re.IGNORECASE)
_VOL_OR_AREA_QTY = re.compile(
    r"(\d{1,6}(?:\.\d+)?)\s*(cu\.?\s*m|cum|cubic\s+metre|sq\.?\s*m|sqm|square\s+metre|tonnes?|m2|m3|mt)\b",
    re.IGNORECASE,
)


def _norm_unit(u: str) -> str | None:
    if not u:
        return None
    key = re.sub(r"\s+", "", u.lower())
    return UNIT_MAP.get(key, u.strip())


def _domain_hint(text: str, span: tuple[int, int]) -> str | None:
    """Look at ~120 chars around a number to guess what it measures."""
    s = max(0, span[0] - 120)
    around = text[s : span[1] + 40].lower()
    if "concrete" in around:
        return "concrete_volume"
    if "steel" in around or "reinforcement" in around:
        return "steel_mass"
    if "brickwork" in around or "masonry" in around:
        return "masonry_volume"
    if "plaster" in around:
        return "plaster_area"
    if "excavation" in around or "earthwork" in around:
        return "excavation_volume"
    if "painting" in around:
        return "painting_area"
    return None


def extract(text: str) -> list[QuantityMention]:
    out: list[QuantityMention] = []

    for m in _GRADE_CONCRETE.finditer(text):
        out.append(QuantityMention(
            raw=m.group(0), name="concrete_grade", value=f"M{m.group(1)}", unit=None,
            span_start=m.start(), span_end=m.end(),
        ))
    for m in _GRADE_STEEL.finditer(text):
        out.append(QuantityMention(
            raw=m.group(0), name="steel_grade", value=m.group(1).replace(" ", "").upper(),
            unit=None, span_start=m.start(), span_end=m.end(),
        ))
    for m in _CRORE.finditer(text):
        out.append(QuantityMention(
            raw=m.group(0), name="amount_crore_rs", value=float(m.group(1)), unit="crore",
            span_start=m.start(), span_end=m.end(),
        ))
    for m in _LAKH.finditer(text):
        out.append(QuantityMention(
            raw=m.group(0), name="amount_lakh_rs", value=float(m.group(1)), unit="lakh",
            span_start=m.start(), span_end=m.end(),
        ))
    for m in _AGE_DAYS.finditer(text):
        out.append(QuantityMention(
            raw=m.group(0), name="age_days", value=int(m.group(1)), unit="days",
            span_start=m.start(), span_end=m.end(),
        ))
    for m in _STRENGTH.finditer(text):
        out.append(QuantityMention(
            raw=m.group(0), name="strength_MPa", value=float(m.group(1)), unit="MPa",
            span_start=m.start(), span_end=m.end(),
        ))
    for m in _TOLERANCE.finditer(text):
        out.append(QuantityMention(
            raw=m.group(0), name=f"tolerance_{m.group(2).lower()}", value=float(m.group(1)),
            unit=m.group(2), span_start=m.start(), span_end=m.end(),
        ))
    for m in _VOL_OR_AREA_QTY.finditer(text):
        unit = _norm_unit(m.group(2))
        hint = _domain_hint(text, (m.start(), m.end())) or "quantity"
        out.append(QuantityMention(
            raw=m.group(0), name=f"{hint}_{unit}" if unit else hint, value=float(m.group(1)),
            unit=unit, span_start=m.start(), span_end=m.end(),
        ))
    return out
