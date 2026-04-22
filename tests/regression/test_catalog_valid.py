"""Regression: standards catalog is parseable and every entry has the required fields."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
CATALOG = ROOT / "standards" / "metadata" / "catalog.yaml"


def test_catalog_parseable():
    data = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    assert isinstance(data, dict) and "entries" in data


def test_entries_have_required_fields():
    data = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    for e in data["entries"]:
        assert e.get("code")
        assert e.get("title")
        assert e.get("source_url")
        assert e.get("priority") in (1, 2, 3)
        assert e.get("local_path")
        assert e.get("license_note")


def test_priority_1_and_2_counts():
    data = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    p1 = [e for e in data["entries"] if e.get("priority") == 1]
    p2 = [e for e in data["entries"] if e.get("priority") == 2]
    assert len(p1) >= 20, f"expected >= 20 priority-1 entries, got {len(p1)}"
    assert len(p2) >= 3, f"expected >= 3 priority-2 entries, got {len(p2)}"
