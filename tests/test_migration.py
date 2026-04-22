import shutil
import tempfile
from pathlib import Path

import pandas as pd


def test_migrate_legacy_flags_csv(tmp_path: Path):
    run_dir = tmp_path / "run_old"
    run_dir.mkdir()
    # emulate a legacy flags.csv (missing keyword_score / llm_score / combined_score)
    legacy_df = pd.DataFrame([
        {"id": "fc_1", "chunk_id": "c1", "category": "F", "span_text": "suitable aggregate", "status": "CONFIRMED"},
    ])
    legacy_df.to_csv(run_dir / "flags.csv", index=False)

    # Ensure result.json exists so the UI loader sees this as a "real" run
    (run_dir / "result.json").write_text("{}", encoding="utf-8")

    from scripts.migrate_legacy_outputs import migrate_dir

    migrated = migrate_dir(tmp_path)
    assert migrated == 1

    df2 = pd.read_csv(run_dir / "flags.csv")
    for col in ("keyword_score", "llm_score", "combined_score", "category_name"):
        assert col in df2.columns
    assert df2["category_name"].iloc[0] == "Undefined Terms"
